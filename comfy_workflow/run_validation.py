"""Submit the exact exported graph and record actual ComfyUI execution results."""
from pathlib import Path
import json
import time
import urllib.request
import urllib.error
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parent
SERVER = "http://127.0.0.1:8190"
NAME = "02_juggernaut_xi_complete"

def request(path, value=None):
    body = None if value is None else json.dumps(value).encode("utf-8")
    req = urllib.request.Request(SERVER + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc

def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def validate_schema(graph, info):
    for nid, node in graph.items():
        cls = node["class_type"]
        if cls not in info:
            raise ValueError(f"Missing node: {cls}")
        schema = info[cls]["input"]
        required = schema.get("required", {})
        optional = schema.get("optional", {})
        if not set(required).issubset(node["inputs"]):
            raise ValueError(f"Missing required input for {nid}: {cls}")
        for field, value in node["inputs"].items():
            entry = (required | optional)[field]
            typ = entry[0]
            if isinstance(value, list):
                source_id, slot = value
                source = graph[source_id]
                actual = info[source["class_type"]]["output"][slot]
                if actual != typ:
                    raise ValueError(f"Type mismatch: {source_id}:{slot} -> {nid}.{field}")
            elif isinstance(typ, list):
                if value not in typ:
                    raise ValueError(f"Unavailable option: {nid}.{field}={value}")
            elif typ in ("INT", "FLOAT") and len(entry) > 1:
                opts = entry[1]
                if not opts.get("min", value) <= value <= opts.get("max", value):
                    raise ValueError(f"Out-of-range value: {nid}.{field}={value}")
    print(f"Schema OK: {len(graph)} nodes and all model/parameter/type references", flush=True)

def main():
    graph = json.loads((ROOT / f"{NAME}.api.json").read_text(encoding="utf-8"))
    workflow = json.loads((ROOT / f"{NAME}.json").read_text(encoding="utf-8"))
    info = request("/object_info")
    validate_schema(graph, info)
    stats = request("/system_stats")
    write("system_stats.json", stats)
    start = time.perf_counter()
    queued = request("/prompt", {"prompt": graph, "client_id": "scp-workflow-validation", "extra_data": {"extra_pnginfo": {"workflow": workflow}}})
    write("queue_response.json", queued)
    if queued.get("node_errors"):
        raise ValueError(queued["node_errors"])
    prompt_id = queued["prompt_id"]
    print(f"Queued {prompt_id}", flush=True)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        histories = request(f"/history/{prompt_id}")
        if prompt_id in histories:
            history = histories[prompt_id]
            write("execution_history.json", history)
            elapsed = time.perf_counter() - start
            status = history.get("status", {})
            if status.get("status_str") != "success":
                write("validation_result.json", {"success": False, "elapsed_seconds": round(elapsed, 2), "status": status})
                raise RuntimeError(json.dumps(status, ensure_ascii=False))
            images = []
            for node_id, output in history["outputs"].items():
                for image in output.get("images", []):
                    path = ROOT / "output" / image["subfolder"] / image["filename"]
                    with Image.open(path) as im:
                        rgb = im.convert("RGB")
                        entry = {"node": node_id, "path": str(path), "size": list(im.size), "rgb_mean": ImageStat.Stat(rgb).mean, "extrema": rgb.getextrema(), "workflow_metadata": "workflow" in im.info, "prompt_metadata": "prompt" in im.info}
                        images.append(entry)
                        print(f"Saved {im.width}x{im.height}: {path.name}", flush=True)
            result = {"success": True, "schema_validation": "passed", "prompt_id": prompt_id, "elapsed_seconds": round(elapsed, 2), "images": images}
            write("validation_result.json", result)
            print(f"SUCCESS in {elapsed:.1f} seconds", flush=True)
            return
        time.sleep(2)
    raise TimeoutError("ComfyUI did not complete within 20 minutes; inspect the queue before retrying.")

if __name__ == "__main__":
    main()
