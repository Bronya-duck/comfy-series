"""Install the pinned public H94 weights through the project's budgeted downloader."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comfy_series.assets import download
from comfy_series.common import Config, Store, read_json, write_json

config = Config()
store = Store(config)
series = store.create_series(series_id="SC-REFERENCE", name="参考功能验收", isolated=True)
results = []
for spec in read_json(config.data / "reference_assets.json"):
    print(f"Downloading {spec['name']} ({spec['expected_bytes']} bytes)", flush=True)
    result = download(store, spec, series["id"])
    results.append(result)
    print(f"Verified SHA256 {result['asset']['sha256']}", flush=True)
write_json(config.data / "reference_installation.json", results)
print("Reference assets ready", flush=True)
