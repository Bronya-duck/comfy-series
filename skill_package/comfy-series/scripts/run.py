"""Find this skill's project and invoke its isolated runtime without shell interpolation."""
import json
import subprocess
import sys
from pathlib import Path

root = next((p for p in Path(__file__).resolve().parents if (p / "comfy_series.json").is_file()), None)
if root is None:
    print(json.dumps({"ok": False, "error": {"code": "project_missing", "message": "未找到comfy_series.json"}}))
    raise SystemExit(2)
runtime = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
if not runtime.is_file():
    print(json.dumps({"ok": False, "error": {"code": "runtime_missing", "message": "运行项目setup_comfy_series.ps1建立独立环境"}}))
    raise SystemExit(2)
raise SystemExit(subprocess.call([str(runtime), "-m", "comfy_series", "--project", str(root), *sys.argv[1:]], cwd=root))
