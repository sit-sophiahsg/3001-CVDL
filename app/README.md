# FreshMart produce scale UI

Run from the repository root:

```powershell
pip install -r app/requirements.txt
streamlit run app/app.py
```

Mode 2 follows the shopper flow: idle, image input, produce selection, simulated
weighing, result, and label printout. Mode 1 reuses the last scan and shows boxes,
confidence values, freshness curves, forecasts, overlays, and the rule trace.

All model output is produced by `app/backend.py:analyse`. It is currently a
CPU-only stand-in and is the only integration point for the real models later.
Prices are placeholder values in `configs/prices.csv`; scan logs are written to
`logs/scans.csv` at runtime.
