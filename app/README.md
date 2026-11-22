# FreshMart produce scale UI

Run from the repository root:

```powershell
pip install -r app/requirements.txt
streamlit run app/app.py
```

Both modes open on a live camera view (`app/live_component`, a Streamlit component with no
build step). The detector named in `deploy_config.json` runs in the browser with
onnxruntime-web (WebGPU if available, else WebAssembly), loaded from the Hub and kept in the
browser's Cache API. It draws a labelled box on every frame (about 10 fps at most). When the
scene has been still for 1.5 s, the frame is sent once to Python, which grades it with
`pipeline.analyse_real` and sends the grades back for the chips. The shopper picks the type
before or after placing the items. Model view adds toggles for boxes, freshness %, blemish
mask and occlusion map (item #1), the Decision / Items / Curve / Log tabs, and a Developer box
(Simulate outcome, Simulated weight, Upload photo (backup)). The camera needs https or
localhost.

"Auto (models decide)" runs the trained ONNX models (`app/pipeline.py:analyse_real`),
downloaded from the Hugging Face model repo `sophiahsgsit/freshmart-models` by
`app/models.py` (override with `FRESHMART_MODELS_REPO`, pin with
`FRESHMART_MODELS_REVISION`, or load a local folder with `FRESHMART_MODELS_DIR`).
Decisions come from the shared rule engine `src/pricing.py`. Forcing a rule (1-7) in
Model view uses the stand-in `app/backend.py:analyse` instead.

Prices, messages and thresholds come only from the bundle's `prices.csv` and
`rules.yaml`. `python app/fetch_models.py` downloads the whole bundle ahead of time.
Scan logs (time, selected type, rule, staff alert; never photos) are written to
`$FRESHMART_LOG_DIR/scans.csv` (default `logs/scans.csv`).
