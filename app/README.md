# FreshMart produce scale UI

Run from the repository root:

```powershell
pip install -r app/requirements.txt
streamlit run app/app.py
```

Mode 2 follows the shopper flow: idle, image input, produce selection, simulated
weighing, result, and label printout. Mode 1 reuses the last scan and shows boxes,
confidence values, freshness curves, forecasts, overlays, and the rule trace.

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
