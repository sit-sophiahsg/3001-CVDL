/* FreshMart live scale: camera + in-browser detector + auto-scan, as a Streamlit component.
 *
 * No build step. Talks to Streamlit with the component postMessage protocol:
 *   out: streamlit:componentReady, streamlit:setComponentValue, streamlit:setFrameHeight
 *   in:  streamlit:render (args from Python)
 *
 * The detector runs here on every frame (<= ~10 fps, never queued). Pre- and post-processing
 * follow app/pipeline.py: letterbox to 640 with grey 114, RGB / 255, decode [1, 10, 8400],
 * confidence >= 0.25, class-agnostic NMS at IoU 0.7, top class per box, at most 12 boxes.
 * When the scene has been still for 1.5 s the frame is sent once to Python, which grades it with
 * the same code as the notebook (pipeline.analyse_real) and passes the grades back as args.
 */
(function () {
  "use strict";

  const DET_SIZE = 640, DET_CONF = 0.25, DET_IOU = 0.7, MAX_ITEMS = 12;
  const MIN_PERIOD_MS = 100;            // cap at ~10 fps
  const STILL_MS = 1500, STILL_IOU = 0.85, CHANGE_IOU = 0.6, CHANGE_FRAMES = 3;
  const CAPTURE_SIDE = 1280, CAPTURE_QUALITY = 0.9;
  const BOX_BLUE = "#2B7FD6", TYPE_BG = "#0E2A47", GREY = "#5E6B64";
  const TIER = { A: "#1F6F47", B: "#9A5300", C: "#B23A12", D: "#8A1C0E" };
  const CACHE = "freshmart-models-v1";

  // ------------------------------------------------------------ Streamlit protocol
  function send(type, data) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data || {}), "*");
  }
  function setValue(value) { send("streamlit:setComponentValue", { value: value, dataType: "json" }); }
  let frameHeight = 0;
  function setHeight(h) {
    h = Math.round(h);
    if (h !== frameHeight) { frameHeight = h; send("streamlit:setFrameHeight", { height: h }); }
  }

  // ------------------------------------------------------------ elements + state
  const $ = (id) => document.getElementById(id);
  const stage = $("stage"), view = $("view"), ctx = view.getContext("2d"), video = $("video");
  const letter = document.createElement("canvas"); letter.width = letter.height = DET_SIZE;
  const lctx = letter.getContext("2d", { willReadFrequently: true });

  let args = {};
  let session = null, inputName = "images", classes = [];
  let detUrl = null, camStarted = false, camError = null, modelError = null;
  let boxes = [];                     // live boxes, video pixels: {box:[x0,y0,x1,y1], cls, conf}
  let prevBoxes = [];
  let armed = true, stillSince = null, changeCount = 0;
  let capTs = null, capBoxes = null, capScale = 1, checking = false;
  let grades = null;                  // args.grades adopted for capTs
  const dismissed = new Set();        // ts values whose grades must not come back
  let lastRearm = null;
  let still = null, stillImg = null, stillSrc = null;
  const imgCache = new Map();         // data URI -> HTMLImageElement
  const stats = { fps: 0, frames: 0, scans: 0, times: [], lastMs: 0, inferMs: 0, backend: null };
  window.__liveStats = stats;

  // ------------------------------------------------------------ geometry
  function iou(a, b) {
    const x0 = Math.max(a[0], b[0]), y0 = Math.max(a[1], b[1]), x1 = Math.min(a[2], b[2]), y1 = Math.min(a[3], b[3]);
    const inter = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
    const ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
    return ua > 0 ? inter / ua : 0;
  }
  // Greedy one-to-one match; returns, for each box in a, [index in b, IoU] (index -1 if none left).
  function match(a, b) {
    const used = new Set();
    return a.map((x) => {
      let best = -1, bestIou = 0;
      b.forEach((y, j) => { if (!used.has(j)) { const v = iou(x, y); if (v > bestIou) { bestIou = v; best = j; } } });
      if (best >= 0) used.add(best);
      return [best, bestIou];
    });
  }
  function sameScene(a, b, thr) {
    return a.length === b.length && match(a, b).every((m) => m[0] >= 0 && m[1] >= thr);
  }

  // ------------------------------------------------------------ detector
  async function cachedModel(url) {
    if ("caches" in window) {
      try {
        const cache = await caches.open(CACHE);
        let resp = await cache.match(url);
        if (!resp) {
          resp = await fetch(url, { mode: "cors" });
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          await cache.put(url, resp.clone());
        }
        return new Uint8Array(await resp.arrayBuffer());
      } catch (e) { console.warn("Cache API failed, plain fetch", e); }
    }
    const resp = await fetch(url, { mode: "cors" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return new Uint8Array(await resp.arrayBuffer());
  }

  async function loadDetector(url) {
    try {
      ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/";
      const bytes = await cachedModel(url);
      // WebGPU where the browser has it (much faster), else WebAssembly on the CPU
      const tries = navigator.gpu ? [["webgpu"], ["wasm"]] : [["wasm"]];
      let lastErr = null;
      for (const eps of tries) {
        try {
          session = await ort.InferenceSession.create(bytes, { executionProviders: eps, graphOptimizationLevel: "all" });
          stats.backend = eps[0];
          break;
        } catch (e) { lastErr = e; session = null; console.warn("detector backend " + eps[0] + " failed", e); }
      }
      if (!session) throw lastErr;
      inputName = session.inputNames[0];
      modelError = null;
    } catch (e) {
      modelError = "The live detector could not be loaded (" + (e && e.message ? e.message : e) + ").";
      console.error(e);
    }
  }

  async function detect(source, w, h) {
    const r = Math.min(DET_SIZE / h, DET_SIZE / w);
    const nw = Math.round(w * r), nh = Math.round(h * r);
    const left = Math.round((DET_SIZE - nw) / 2 - 0.1), top = Math.round((DET_SIZE - nh) / 2 - 0.1);
    lctx.fillStyle = "rgb(114,114,114)";
    lctx.fillRect(0, 0, DET_SIZE, DET_SIZE);
    lctx.drawImage(source, left, top, nw, nh);
    const px = lctx.getImageData(0, 0, DET_SIZE, DET_SIZE).data;
    const n = DET_SIZE * DET_SIZE, x = new Float32Array(3 * n);
    for (let i = 0, p = 0; i < n; i++, p += 4) {
      x[i] = px[p] / 255; x[n + i] = px[p + 1] / 255; x[2 * n + i] = px[p + 2] / 255;
    }
    const feeds = {}; feeds[inputName] = new ort.Tensor("float32", x, [1, 3, DET_SIZE, DET_SIZE]);
    const tRun = performance.now();
    const out = (await session.run(feeds))[session.outputNames[0]];
    stats.inferMs = performance.now() - tRun;
    const d = out.data, rows = out.dims[1], N = out.dims[2], nc = rows - 4;
    const cand = [];
    for (let i = 0; i < N; i++) {
      let best = 0, cls = 0;
      for (let c = 0; c < nc; c++) { const s = d[(4 + c) * N + i]; if (s > best) { best = s; cls = c; } }
      if (best >= DET_CONF) {
        const cx = d[i], cy = d[N + i], bw = d[2 * N + i], bh = d[3 * N + i];
        cand.push({ b: [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], cls: cls, conf: best });
      }
    }
    cand.sort((a, b) => b.conf - a.conf);
    const kept = [];
    for (const c of cand) { if (kept.every((k) => iou(k.b, c.b) <= DET_IOU)) kept.push(c); }
    const found = [];
    for (const k of kept) {
      const x0 = (k.b[0] - left) / r, y0 = (k.b[1] - top) / r, x1 = (k.b[2] - left) / r, y1 = (k.b[3] - top) / r;
      const box = [Math.min(Math.max(Math.floor(x0), 0), w), Math.min(Math.max(Math.floor(y0), 0), h),
                   Math.min(Math.max(Math.ceil(x1), 0), w), Math.min(Math.max(Math.ceil(y1), 0), h)];
      if (box[2] - box[0] >= 2 && box[3] - box[1] >= 2) found.push({ box: box, cls: k.cls, conf: k.conf });
      if (found.length === MAX_ITEMS) break;
    }
    return found;
  }

  // ------------------------------------------------------------ camera
  async function startCamera() {
    camStarted = true;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      camError = "No camera is available here (the camera needs https or localhost).";
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      video.srcObject = stream;
      await video.play().catch(() => {});
      camError = null;
    } catch (e) {
      camError = (e && (e.name === "NotAllowedError" || e.name === "SecurityError"))
        ? "Camera permission was denied." : "No camera was found.";
    }
  }
  const videoReady = () => video.readyState >= 2 && video.videoWidth > 0;

  // ------------------------------------------------------------ scene logic
  function resetScene() {
    if (capTs !== null) dismissed.add(capTs);
    capTs = null; capBoxes = null; grades = null; checking = false;
    armed = true; stillSince = null; changeCount = 0;
  }

  function capture(found) {
    const vw = video.videoWidth, vh = video.videoHeight;
    const s = Math.min(1, CAPTURE_SIDE / Math.max(vw, vh));
    const c = document.createElement("canvas");
    c.width = Math.round(vw * s); c.height = Math.round(vh * s);
    c.getContext("2d").drawImage(video, 0, 0, c.width, c.height);
    const ts = Date.now();
    armed = false; checking = true; capTs = ts; capScale = s; grades = null;
    capBoxes = found.map((b) => b.box.map((v) => Math.round(v * s)));   // frame pixels, as sent
    stats.sent = found.map((b) => ({ cls: classes[b.cls], conf: b.conf }));
    stats.scans += 1;
    setValue({
      kind: "frame", ts: ts, frame: c.toDataURL("image/jpeg", CAPTURE_QUALITY), w: c.width, h: c.height,
      boxes: found.map((b) => [Math.round(b.box[0] * s), Math.round(b.box[1] * s), Math.round(b.box[2] * s),
                               Math.round(b.box[3] * s), b.cls, Math.round(b.conf * 1000) / 1000]),
    });
  }

  // the captured boxes (kept in frame pixels) in video pixels; null until the scale is known
  function capInVideo() {
    if (!capBoxes) return null;
    if (capScale === null) {
      if (!(videoReady() && grades && grades.w)) return null;
      capScale = grades.w / video.videoWidth;
    }
    return capBoxes.map((b) => b.map((v) => v / capScale));
  }

  function step(found, now) {
    const live = found.map((b) => b.box);
    if (capBoxes) {
      const cap = capInVideo();
      // scene changed: the count changes or a box moves (IoU < 0.6), for a few frames in a row
      if (cap) changeCount = sameScene(live, cap, CHANGE_IOU) ? 0 : changeCount + 1;
      if (changeCount >= CHANGE_FRAMES) {
        const ts = capTs;
        resetScene();
        setValue({ kind: "scene", ts: Date.now(), after: ts });
      }
    } else if (armed) {
      if (live.length > 0 && sameScene(live, prevBoxes.map((b) => b.box), STILL_IOU)) {
        if (stillSince === null) stillSince = now;
        if (now - stillSince >= STILL_MS) { stillSince = null; capture(found); }
      } else {
        stillSince = null;
      }
    }
    prevBoxes = found;
  }

  async function loop() {
    for (;;) {
      const t0 = performance.now();
      if (session && !still && videoReady()) {
        try {
          const found = await detect(video, video.videoWidth, video.videoHeight);
          boxes = found;
          step(found, performance.now());
          const t1 = performance.now();
          stats.frames += 1; stats.lastMs = t1 - t0; stats.times.push(t1);
          while (stats.times.length && t1 - stats.times[0] > 2000) stats.times.shift();
          stats.fps = stats.times.length > 1 ? (stats.times.length - 1) * 1000 / (t1 - stats.times[0]) : 0;
          document.body.dataset.fps = stats.fps.toFixed(1);
        } catch (e) { console.error(e); }
      }
      const wait = Math.max(0, MIN_PERIOD_MS - (performance.now() - t0));
      await new Promise((res) => setTimeout(res, wait || 0));
    }
  }

  // ------------------------------------------------------------ args from Python
  function image(uri) {
    if (!uri) return null;
    let im = imgCache.get(uri);
    if (!im) { im = new Image(); im.src = uri; imgCache.set(uri, im); if (imgCache.size > 64) imgCache.delete(imgCache.keys().next().value); }
    return im;
  }

  function onRender(a) {
    args = a || {};
    classes = args.classes || classes;
    if (args.det_url && args.det_url !== detUrl) { detUrl = args.det_url; session = null; loadDetector(detUrl); }
    if (!camStarted) startCamera();
    if (lastRearm === null) lastRearm = args.rearm;
    else if (args.rearm !== lastRearm) { lastRearm = args.rearm; resetScene(); }
    const g = args.grades;
    if (g && g.ts !== undefined && !dismissed.has(g.ts)) {
      if (g.ts !== capTs) {        // a scan this instance did not send (e.g. after switching view)
        capTs = g.ts; armed = false; changeCount = 0;
        capBoxes = (g.cap || []).map((b) => b.slice(0, 4));
        capScale = null;           // frame -> video scale, known once the video is up
      }
      grades = g; checking = false;
      stats.cap = capBoxes; stats.served = (g.items || []).map((it) => ({ cap: it.cap, box: it.box, conf: it.det_conf, produce: it.produce }));
    }
    if (args.still) {
      still = args.still;
      if (still.src !== stillSrc) { stillSrc = still.src; stillImg = image(still.src); }
    } else { still = null; stillImg = null; stillSrc = null; }
    $("back").style.display = still ? "block" : "none";
    resize();
  }

  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "streamlit:render") onRender(event.data.args);
  });
  $("back").addEventListener("click", () => setValue({ kind: "live", ts: Date.now() }));

  // ------------------------------------------------------------ drawing
  function resize() {
    const w = stage.clientWidth || document.body.clientWidth || 640;
    const h = Math.max(300, Math.min(args.max_height || 620, Math.round(w * (args.aspect || 0.62))));
    stage.style.height = h + "px";
    stage.style.setProperty("--h", h + "px");
    const dpr = window.devicePixelRatio || 1;
    if (view.width !== Math.round(w * dpr) || view.height !== Math.round(h * dpr)) {
      view.width = Math.round(w * dpr); view.height = Math.round(h * dpr);
    }
    setHeight(h);
  }
  window.addEventListener("resize", resize);

  // grade for a live box: the captured box it matches, then the server item matched to that box
  function gradeFor(liveBoxes) {
    const out = liveBoxes.map(() => null);
    const cap = capInVideo();
    if (!grades || !cap || !grades.items) return out;
    const byCap = new Map(grades.items.filter((it) => it.cap !== null && it.cap !== undefined).map((it) => [it.cap, it]));
    match(liveBoxes, cap).forEach((m, i) => { if (m[0] >= 0 && m[1] >= CHANGE_IOU) out[i] = byCap.get(m[0]) || null; });
    return out;
  }

  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

  function draw() {
    requestAnimationFrame(draw);
    const W = view.width, H = view.height, dpr = window.devicePixelRatio || 1;
    ctx.fillStyle = "#0F1A15"; ctx.fillRect(0, 0, W, H);
    const model = args.view === "model";
    const src = still ? stillImg : (videoReady() ? video : null);
    const sw = still ? still.w : video.videoWidth, sh = still ? still.h : video.videoHeight;
    let msg = null;
    if (still && !(stillImg && stillImg.complete)) msg = "Loading the photo…";
    else if (!still && camError) msg = camError + " Use “Upload photo (backup)” in Model view (Developer box) instead.";
    else if (!still && !videoReady()) msg = "Starting the camera…";
    else if (!still && modelError) msg = modelError;
    else if (!still && !session) msg = "Loading the live detector…";

    let shown = [], graded = [];
    if (src && sw && sh) {
      const k = Math.min(W / sw, H / sh), ox = (W - sw * k) / 2, oy = (H - sh * k) / 2;
      ctx.drawImage(src, ox, oy, sw * k, sh * k);
      if (still) {
        shown = (still.items || []).map((it) => ({ box: it.box, cls: -1, conf: it.det_conf, produce: it.produce }));
        graded = still.items || [];
      } else {
        shown = boxes;
        graded = gradeFor(boxes.map((b) => b.box));
      }
      const T = (b) => [ox + b[0] * k, oy + b[1] * k, ox + b[2] * k, oy + b[3] * k];
      // the server's box for a grade, in the source's pixels
      const srvBox = (g) => {
        if (still) return g.box;
        const s = capScale || 1;
        return g.box.map((v) => v / s);
      };
      // occlusion heat (item #1) and blemish masks, from the last scan, under the boxes
      graded.forEach((g) => {
        if (!g) return;
        if (model && args.show_occ && g.heat) {
          const im = image(g.heat), b = T(srvBox(g));
          if (im && im.complete) { ctx.globalAlpha = g.heat_alpha || 0.45; ctx.drawImage(im, b[0], b[1], b[2] - b[0], b[3] - b[1]); ctx.globalAlpha = 1; }
        }
        if (model && args.show_blemish && g.mask) {
          const im = image(g.mask), b = T(srvBox(g));
          if (im && im.complete) ctx.drawImage(im, b[0], b[1], b[2] - b[0], b[3] - b[1]);
        }
      });
      const showLabels = model ? !!args.show_boxes : true;
      const showFresh = model ? !!args.show_fresh : true;
      const font = 13 * dpr, lh = 20 * dpr;
      ctx.font = "700 " + font + "px Inter, system-ui, sans-serif";
      shown.forEach((b, i) => {
        const g = graded[i];
        const tier = g && g.tier;
        const known = !!(g && g.freshness !== null && g.freshness !== undefined);
        const r = T(b.box);
        const colour = known && showFresh ? (TIER[tier] || BOX_BLUE) : BOX_BLUE;
        if (showLabels || !model) {
          ctx.lineWidth = 3.5 * dpr; ctx.strokeStyle = colour;
          ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(r[0], r[1], r[2] - r[0], r[3] - r[1], 4 * dpr); else ctx.rect(r[0], r[1], r[2] - r[0], r[3] - r[1]); ctx.stroke();
        }
        const lines = [];
        const type = b.produce || classes[b.cls] || "item";
        if (showLabels) lines.push([(model ? "#" + (i + 1) + " " : "") + cap(type) + (model ? " " + Number(b.conf).toFixed(2) : ""), TYPE_BG, 700]);
        if (showFresh) {
          if (known) lines.push([Math.round(g.freshness * 100) + "% fresh" + (model && tier ? " · " + tier : ""), TIER[tier] || GREY, 600]);
          else if (checking) lines.push(["grading…", GREY, 600]);
        }
        if (!lines.length) return;
        let cy = r[1] - lines.length * lh; if (cy < 4 * dpr) cy = r[1] + 4 * dpr;
        lines.forEach((l, j) => {
          ctx.font = l[2] + " " + font + "px Inter, system-ui, sans-serif";
          const wch = ctx.measureText(l[0]).width + 14 * dpr;
          ctx.fillStyle = l[1]; ctx.fillRect(r[0], cy + j * lh, wch, lh);
          ctx.fillStyle = "#FFFFFF"; ctx.fillText(l[0], r[0] + 7 * dpr, cy + j * lh + 14 * dpr);
        });
      });
    }
    if (!msg && !still && session && videoReady() && shown.length === 0) msg = "Camera is live. Place items on the tray.";
    $("msg").style.display = msg ? "flex" : "none";
    if (msg) $("msgtext").textContent = msg;

    const n = shown.length;
    $("count").textContent = n ? n + (n === 1 ? " item" : " items") + " detected" : "no items";
    $("livetext").textContent = still ? "UPLOADED PHOTO" : model ? "LIVE · boxes every frame · " + stats.fps.toFixed(1) + " fps" : "LIVE";
    const progress = !still && armed && stillSince !== null ? Math.min(1, (performance.now() - stillSince) / STILL_MS) : null;
    $("ring").style.display = progress !== null && !model ? "flex" : "none";
    $("ringtext").style.display = progress !== null && model ? "block" : "none";
    if (progress !== null) {
      $("ringarc").setAttribute("stroke-dashoffset", (88 * (1 - progress)).toFixed(1));
      $("ringtext").textContent = "Scene still · auto-scan in " + ((1 - progress) * STILL_MS / 1000).toFixed(1) + " s";
    }
    $("scanline").style.display = checking || args.checking ? "block" : "none";
    stage.dataset.state = still ? "still" : checking ? "checking" : capBoxes ? (grades && grades.items && grades.items.length ? "graded" : "captured") : progress !== null ? "holding" : "live";
  }

  send("streamlit:componentReady", { apiVersion: 1 });
  resize();
  requestAnimationFrame(draw);
  loop();
})();
