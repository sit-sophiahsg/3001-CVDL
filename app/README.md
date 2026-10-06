# FreshScale - produce quality scale (UI prototype)

Streamlit UI for the supermarket produce quality detection project. Right now it uses a
**fake predictor**. The trained model will be added later by replacing `predictor.py` only.

## Run

From the repo root (Windows PowerShell):

```powershell
uv venv app/.venv --python 3.12          # first time only
uv pip install -r app/requirements.txt --python app/.venv
app\.venv\Scripts\activate
streamlit run app/app.py
```

Then open http://localhost:8501.

### On a phone
Connect the phone to the same Wi-Fi network and open the **Network URL** that Streamlit prints
(e.g. `http://192.168.x.x:8501`). Browsers only allow the live camera on HTTPS or localhost,
so over plain `http://` the **Camera** tab may stay blank. If that happens, use the
**Upload photo** tab, which lets you take a picture with the phone's own camera app. For live
camera access on a phone, deploy the app on Streamlit Community Cloud (HTTPS).

## Files

| File | Purpose |
|------|---------|
| `app.py` | Screens (Home, Item grid, Scan, Result) and navigation |
| `predictor.py` | `predict(image, selected_id) -> dict`. The only file the real model replaces (see the comment at the top) |
| `pricing.py` | Config loading, price and discount calculation |
| `styles.py` | Custom CSS |
| `config.yaml` | Items, prices per kg, enabled flags, discount rules, currency. Edit this file without touching the code |

## Demo rehearsal
Open the sidebar (`>` at the top left) and use **Demo controls** to force an outcome:
Auto, Fresh, Rotten, Invalid scan or Mismatch. With **Auto**, the result comes from a hash of the
photo, so the same photo always gives the same result. The result screen shows a
"DEMO MODE" banner while the fake predictor is active.
