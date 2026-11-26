# Freshness-Aware Pricing: Computer Vision for Supermarket Produce Quality 

**AAI3001 Deep Learning and Computer Vision**

---

## Team · Group P1-9

| Student ID | Member |
|---|---|
| 2503845 | Gador Sophia Helen Santiago |
| 2501526 | Natalie Peh |
| 2501354 | Tan Jian Ying Ivan |
| 2500492 | Tan Jing Yu |
| 2502353 | Tan Jun Ying |

---

A self-service produce scale with a camera. It finds each item, grades how fresh it is, and prices it by freshness: full price, 20% off, 50% off, or not for sale. When the models aren't sure, it asks for a rescan or a staff check instead of guessing.

- **Live app:** https://3001-cvdl-p1-9.streamlit.app/
- **Notebook (Colab):** https://colab.research.google.com/drive/1O9Mwf8CpvcNl5it8uUBO_Dyr5bH4qsmA?usp=sharing
- **Models (Hugging Face):** https://huggingface.co/sophiahsgsit/freshmart-models

> Coursework only. Not tested for real retail use.

---

## How it works

| Goal | Model | What it does | Sets the price? |
|---|---|---|---|
| 1 · Detection | YOLO11n (`own_ft`) | Boxes and counts every item | Yes |
| 2 · Freshness | ResNet-50, four heads (`r50_coral`) | Type, freshness %, tier, days left | Yes |
| 3 · Blemish | U-Net, MobileNetV2 encoder (`unet_bce`) | Marks bruised or mouldy pixels | No, explains only |
| 4 · Forecast | U-Net generator, L1 (`l1_only`) | Pictures at +1 / +3 / +7 days | No, illustrations only (experimental) |

**One scan:**
1. The detector runs live in the browser (onnxruntime-web, about 9 fps with WebGPU).
2. When the scene is still for 1.5 s, one frame goes to the server.
3. The server runs detection, freshness and blemish, then the 7 pricing rules.
4. The app shows one message and one price.

**Price** = weight × price per kg × (1 − tier discount). The demo uses a fixed weight of 0.25 kg

| Tier | Freshness | Price |
|---|---|---|
| A | ≥ 70% | full price |
| B | 40–69% | 20% off |
| C | 15–39% | 50% off |
| D | < 15% | not for sale, staff alerted |

**The 7 rules** (checked in order, first match wins): not recognised · not confident (rescan) · mixed types · wrong selection · confidently rotten · unsure rotten (rescan) · price. The thresholds (`rules.yaml`) and prices per kg (`prices.csv`) are part of the model bundle on Hugging Face, next to the models, so they can be changed without retraining.

**Two views:**
- **Shopper:** pick the produce first, then place it on the scale. The camera starts, the scale scans by itself once the items are still, and it shows one message and one price. A price stays on screen until *Next item* or *Reset scan*; *Why this price?* shows the freshness, blemishes, the price formula and the forecast pictures.
- **Model view:** every model's output for one scan (boxes, freshness %, tier, days left, blemish mask, occlusion map, forecast, rule checklist). The type comes from the detector, not from a tile. The first still scene is captured and held on screen until *Reset scan*.

**Demo mode** (for the presentation): our freshness model does not transfer well to a webcam. Loosening the rules for our camera sold more rotten produce, so the real rules were kept. Demo mode trusts a confident detection (≥ 0.80), skips the freshness rules (1, 2 and 6) and prices with a camera-tuned model. The detector rules still apply (mixed types, wrong selection), and the real model's verdict is still shown underneath.

---

## Results (frozen test sets)

| Goal | Metric | Baseline | Ours |
|---|---|---|---|
| Detection | mAP@0.5 | 0.31 (COCO YOLO11n) | 0.873 |
| Freshness | Tier macro-F1 | 0.32 (hurdle model) | 0.42, plus days left (±7.5 days) |
| Blemish | IoU | 0.30 (HSV colour rule) | 0.60 |
| Forecast | Freshness gap at +7 days | 0.131 ("no change") | 0.140 (L1 only, deployed); 0.095 (L1 + GAN) |
| Pricing rules | Rotten sold / good food binned | 9.1% / 27.7% (no rules) | 6.2% / 7.6% |

All four models run on CPU as ONNX fp32. INT8 was tried and rejected because it failed accuracy rules set before measuring.

---

## Run it locally

**You need:** Python 3.11, Git, a webcam, and an internet connection the first time. On first start the app downloads the model bundle (about 375 MB) from the Hugging Face Hub and caches it, so later starts are quick. No token is needed; the repo is public.

**1. Get the code**

```bash
git clone https://github.com/sit-sophiahsg/3001-CVDL.git
cd 3001-CVDL
```

**2. Create a virtual environment and install the packages**

macOS / Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r app/requirements.txt
```

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\activate.bat` from Command Prompt.

**3. Start the app** (from the repository root, with the environment active)

```bash
streamlit run app/app.py
```

**4. Open it**

Go to http://localhost:8501 and allow camera access when the browser asks. The camera only works on `localhost` or `https`. Chrome or Edge with WebGPU gives the smoothest live detection; other browsers fall back to WebAssembly (about 1–2 fps).

**5. Try a scan**

- *Shopper:* pick a produce tile, then hold the item still in front of the camera for 1.5 s.
- *Model view:* switch at the top of the page; the first still scene is captured and held. Press *Reset scan* for a new one.

**Troubleshooting**

- *"The trained models could not be loaded"*: check the internet connection. To run offline, download the bundle once and point the app at it with `FRESHMART_MODELS_DIR=<folder>`.
- *No camera picture*: allow camera access in the browser's site settings and make sure no other app is using the webcam, then reload.
- *Model view's developer box*: "Simulate outcome" forces a rule (1–7) with stand-in numbers, so every rule can be shown without the right produce at hand.

**With Docker:**

```bash
docker build -t freshmart .
docker run -p 8501:8501 freshmart
```

The image downloads the models while it builds, so it starts without needing the internet.

---

## Repository layout

```
app/
  app.py              # Streamlit entry point: state, scanning, view switch
  mode1.py, mode2.py  # Model view and Shopper view
  pipeline.py         # detector → freshness → blemish → forecast (ONNX)
  models.py           # downloads and loads the model bundle from Hugging Face
  live.py             # bridge to the in-browser live detector
  live_component/     # in-browser live detector (onnxruntime-web)
  backend.py          # stand-in results for "Simulate outcome"
  components.py       # shared UI pieces and styles
  views.py            # image overlays (boxes, blemish mask)
  fetch_models.py     # pre-downloads the models (used by the Docker build)
  demo/               # sample photos
  requirements.txt
src/
  pricing.py          # the 7 pricing rules (same file the notebook tests)
AAI3001_P1_9.ipynb    # training and evaluation notebook
Dockerfile
```

Thresholds (`rules.yaml`) and prices (`prices.csv`) are in the [model bundle](https://huggingface.co/sophiahsgsit/freshmart-models), not in this repo.

---

## Data

- **Kaggle:** [Fresh and Stale Classification](https://www.kaggle.com/datasets/swoyam2609/fresh-and-stale-classification), 26,655 images of six types
- **Timelapse:** 18 public YouTube videos of produce decaying, labelled with freshness % from each item's cutoff day
- **Our own photos:** 146 taken, 112 kept (piles, bags, counters), boxes auto-labelled with Grounding DINO and checked by hand
- **Blemish masks:** 240 drawn in Roboflow with SAM assistance

Scope: apple, banana, orange, capsicum, tomato, potato.

---

## Limitations

- One training timelapse video per type, so unfamiliar produce can get the wrong freshness level
- The freshness model doesn't transfer well to our webcam (hence demo mode)
- Our own photos are all fresh, so rotten produce on our camera is untested
- 40% of timelapse test scans need a rescan or staff check: the cost of safety
