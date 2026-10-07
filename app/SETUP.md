# FreshScale setup

How to run the FreshScale Streamlit app with the trained ONNX model on your own machine.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (recommended) or plain `pip`
- The model files exported from the Colab notebook (`CVDL_Project.ipynb`):
  - `best_config.json`
  - `produce_fp32.onnx` (about 94 MB)

## 1. Create the environment and install dependencies

Run these from the repo root in Windows PowerShell.

With uv:

```powershell
uv venv app/.venv --python 3.12
uv pip install -r app/requirements.txt --python app/.venv
```

With pip:

```powershell
python -m venv app/.venv
app\.venv\Scripts\python -m pip install -r app/requirements.txt
```

You only need to do this once, and again whenever `requirements.txt` changes.

## 2. Run the app

```powershell
app\.venv\Scripts\activate
streamlit run app/app.py
```

Open http://localhost:8501 in your browser.

When the model loads, the terminal prints a line like this:

```
[predictor] loaded produce_fp32.onnx (resnet50, val F1 0.9954)
```

To stop the app, press `Ctrl+C` in the terminal.

## Using a phone

Connect the phone to the same Wi-Fi network as your computer, then open the **Network URL**
that Streamlit prints (for example `http://192.168.x.x:8501`).

Browsers only allow live camera access on HTTPS or localhost. Over plain `http://`, the
**Camera** tab may stay blank. If it does, use the **Upload photo** tab, which lets you take a
photo with the phone's own camera app.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: onnxruntime` | The venv is not active, or dependencies are missing. Activate it and rerun the install step. |
| `FileNotFoundError` for `best_config.json` or `.onnx` | The model files are not in `app/models/`. Check the file names. |
| Every photo returns "invalid scan" | The photo doesn't look like the training data. Try a clear photo of a single item on a plain background. |
| `activate` is blocked in PowerShell | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activating and run `app\.venv\Scripts\streamlit run app/app.py`. |
| Port 8501 already in use | Stop the other Streamlit instance, or run `streamlit run app/app.py --server.port 8502`. |
