"""Download the FreshMart model bundle into the Hugging Face cache (run at Docker build time).

Fetches deploy_config.json, every model file it names under ``files`` (FP32 only) and the three
configs (rules.yaml, prices.csv, fresh_residuals.npz), plus the optional display-only
``files.freshness_display`` if named (skipped if missing). Honours FRESHMART_MODELS_REPO,
FRESHMART_MODELS_REVISION and FRESHMART_MODELS_DIR, like the app.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import CONFIG_NAME, bundle_files, display_file, download_bundle  # noqa: E402


def main() -> None:
    folder = download_bundle(include_models=True)
    deploy = json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))
    for name in [CONFIG_NAME] + bundle_files(deploy):
        path = folder / name
        if not path.exists():
            raise SystemExit(f"missing after download: {name}")
        print(f"{name:24s} {path.stat().st_size / 1e6:8.1f} MB")
    extra = display_file(deploy)
    if extra:                                       # optional, display only
        path = folder / extra
        print(f"{extra:24s} {path.stat().st_size / 1e6:8.1f} MB (display only)" if path.exists()
              else f"{extra:24s}  not found, skipped (display only)")
    print(f"bundle ready in {folder}")


if __name__ == "__main__":
    main()
