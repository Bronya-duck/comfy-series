from __future__ import annotations
import json
from pathlib import Path
import httpx
from .common import SeriesError, digest


class ComfyClient:
    def __init__(self, config):
        self.config = config
        self.http = httpx.Client(base_url=config.server, timeout=30, trust_env=False)

    def request(self, method, path, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
            if response.is_error:
                try:
                    details = response.json()
                except ValueError:
                    details = {"status": response.status_code}
                raise SeriesError("comfy_http_error", "ComfyUI 请求失败", details)
            return response.json() if response.content else {"ok": True}
        except httpx.RequestError as exc:
            if method == "POST" and path == "/prompt":
                raise SeriesError("submission_unknown", "提交响应中断，服务器可能已接收；先恢复跟踪，不能重复提交", {"client_id": kwargs.get("json", {}).get("client_id")}) from exc
            raise SeriesError("comfy_unavailable", "无法连接 ComfyUI；检查本地服务和端口", {"server": self.config.server}) from exc

    def info(self):
        return self.request("GET", "/object_info")

    def stats(self):
        return self.request("GET", "/system_stats")

    def queue(self):
        return self.request("GET", "/queue")

    def upload(self, path):
        path = Path(path)
        # ComfyUI 0.3.64's LoadImage choices list only the input root.
        name = "ComfySeries_" + digest(path)[:20] + path.suffix.lower()
        with path.open("rb") as stream:
            result = self.request("POST", "/upload/image", files={"image": (name, stream, "application/octet-stream")},
                                  data={"overwrite": "false", "type": "input", "subfolder": ""})
        return (result.get("subfolder", "").rstrip("/") + "/" + result["name"]).lstrip("/")

    def submit(self, graph, canvas, client_id):
        return self.request("POST", "/prompt", json={"prompt": graph, "client_id": client_id,
                           "extra_data": {"extra_pnginfo": {"workflow": canvas}}})

    def history(self, prompt_id):
        return self.request("GET", f"/history/{prompt_id}").get(prompt_id)

    def find_submission(self, client_id, prefix):
        matches = {}
        queue = self.queue()
        prompts = [x for group in ("queue_running", "queue_pending") for x in queue.get(group, [])]
        prompts += [x["prompt"] for x in self.request("GET", "/history").values()]
        for prompt in prompts:
            if prompt[3].get("client_id") == client_id and any(n.get("class_type") == "SaveImage" and n.get("inputs", {}).get("filename_prefix") == prefix for n in prompt[2].values()):
                matches[prompt[1]] = prompt
        if len(matches) > 1:
            raise SeriesError("submission_ambiguous", "发现多个匹配任务，需核实输出后处理", {"prompt_ids": list(matches)})
        return next(iter(matches), None)

    def fetch_image(self, value):
        response = self.http.get("/view", params={k: value[k] for k in ("filename", "subfolder", "type") if k in value})
        response.raise_for_status()
        return response.content

    def free_memory(self):
        return self.request("POST", "/free", json={"unload_models": True, "free_memory": True})
