from __future__ import annotations

import html
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from .common import Config, Store, SeriesError, within


def file_url(path):
    return "/file?p=" + quote(str(Path(path).resolve()), safe="")


def e(value):
    return html.escape(str(value), quote=True)


def label(status):
    return {"runtime_passed": "运行通过", "schema_validated": "结构已验证", "unverified": "待验证", "accepted": "已评审",
            "awaiting_visual_review": "待看图", "prepared": "已准备", "failed": "执行失败", "needs_adjustment": "需调整",
            "completed_with_gaps": "存在差距", "running": "生成中", "waiting": "等待恢复"}.get(status, status)


def render(store):
    styles, series, jobs, sources, assets = [store.all(x) for x in ("styles", "series", "jobs", "sources", "assets")]
    css = """
    :root{color-scheme:dark;--bg:#10151c;--card:#18212b;--line:#2b3a49;--text:#e9eff5;--muted:#9dabbc;--accent:#83d6c8}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 'Segoe UI','Microsoft YaHei',sans-serif}
    a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}header{padding:38px 5vw 22px;border-bottom:1px solid var(--line)}
    header h1{margin:0;font-size:32px}header p{color:var(--muted);margin:6px 0 16px}nav{display:flex;gap:24px;flex-wrap:wrap}
    main{max-width:1450px;margin:auto;padding:20px 5vw 60px}section{scroll-margin-top:20px;margin:32px 0}h2{font-size:23px;font-weight:600}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;overflow:hidden}
    .card img{width:100%;aspect-ratio:1.46;object-fit:contain;background:#0c1117;border-radius:7px}.card h3{margin:12px 0 6px;font-size:18px}
    .muted,small{color:var(--muted)}.tag{font-size:12px;padding:3px 8px;background:#243a3c;color:#ade9df;border-radius:30px;display:inline-block;margin:3px}
    .unverified{background:#413527;color:#efd5a6}.links{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px}.stat{font-size:26px;font-weight:600}
    input{background:var(--card);border:1px solid var(--line);color:var(--text);border-radius:7px;padding:12px;width:100%;margin:0 0 20px}
    details{border-top:1px solid var(--line);margin-top:14px;padding-top:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid var(--line)}
    @media(max-width:600px){header,main{padding-left:20px;padding-right:20px}.card{padding:14px}table{font-size:12px}}
    """
    parts = [f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Comfy Series</title><style>{css}</style>",
             "<header><h1>Comfy Series</h1><p>风格、素材和工作流，留在你的本地项目中。</p><nav><a href='#gallery'>图片</a><a href='#styles'>风格</a><a href='#library'>资料库</a><a href='#models'>模型</a><a href='#materials'>素材</a><a href='/'>刷新</a></nav></header><main>",
             f"<div class='grid'><div class='card'><div class='stat'>{len(styles)}</div>风格版本</div><div class='card'><div class='stat'>{len(jobs)}</div>制作请求</div><div class='card'><div class='stat'>{len(sources)}</div>资料来源</div></div>"]
    parts.append("<section id='gallery'><h2>生成图片</h2><div class='grid'>")
    for job in sorted(jobs, key=lambda x:x.get("created_at", ""), reverse=True):
        for image in job.get("images", []):
            path = image.get("best_path") or image.get("latest_path")
            if not path:
                continue
            attempt = next((x for x in image["attempts"] if x.get("path") == path), image["attempts"][-1])
            folder = Path(attempt["folder"])
            review = image.get("review") or {}
            parts.append(f"<article class='card'><a href='{e(file_url(path))}'><img loading='lazy' src='{e(file_url(path))}' alt='{e(job['request']['brief'])}'></a><h3>{e(job['style_key'])} · 第{image['index'] + 1}张</h3><span class='tag'>{e(label(job['status']))}</span><small>{e(attempt.get('output_size'))}</small><p>{e(job['request']['brief'])}</p>")
            parts.append(f"<div class='links'><a href='{e(file_url(folder / 'workflow.json'))}'>画布工作流</a><a href='{e(file_url(folder / 'workflow.api.json'))}'>API 工作流</a><a href='{e(file_url(folder / 'manifest.json'))}'>复现记录</a></div><details><summary>检查与调整记录</summary><pre>{e(json.dumps(review or {'状态':'尚未进行视觉评审'}, ensure_ascii=False, indent=2))}</pre></details></article>")
    parts.append("</div><h3>全部制作记录</h3><div class='card'><table><tr><th>请求</th><th>风格</th><th>状态</th><th>记录</th></tr>")
    for job in sorted(jobs, key=lambda x:x.get("created_at", ""), reverse=True):
        folder=Path(job['folder'])
        parts.append(f"<tr><td>{e(job['id'])}<br><small>{e(job['request']['brief'])}</small></td><td>{e(job['style_key'])}</td><td>{e(label(job['status']))}</td><td><a href='{e(file_url(folder/'job.json'))}'>轮次、错误与评审</a> · <a href='{e(file_url(folder/'models.json'))}'>模型清单</a> · <a href='{e(file_url(folder/'request.json'))}'>制作要求</a></td></tr>")
    parts.append("</table></div></section><section id='styles'><h2>风格档案</h2><div class='grid'>")
    for style in styles:
        baseline = style.get("visual_baseline", {}).get("image_path")
        parts.append("<article class='card'>")
        if baseline and Path(baseline).is_file():
            parts.append(f"<img loading='lazy' src='{e(file_url(baseline))}' alt='风格基准'>")
        parts.append(f"<h3>{e(style['style_key'])} · {e(style.get('display_name', '未命名'))}</h3><p class='muted'>{e(style.get('prompt_blocks', {}).get('fixed_positive_style', ''))}</p><a href='{e(file_url(store.config.data / 'styles' / (style['style_key'] + '.json')))}'>查看风格档案</a></article>")
    parts.append("</div></section><section id='library'><h2>工作流与模型资料库</h2><p class='muted'>运行通过、结构已验证和待验证分别记录；原始网站可直接打开。</p><input id='search' placeholder='搜索风格、模型家族、节点或用途…'><div class='grid'>")
    for source in sources:
        url = source.get("url", "")
        safe_url = url if urlparse(url).scheme in ("http", "https") else "#"
        status = source.get("validation_status", "unverified")
        terms = e(" ".join(map(str, [source.get("title", ""), source.get("summary", ""), source.get("tags", [])])).lower())
        parts.append(f"<article class='card source' data-search='{terms}'><span class='tag {e(status)}'>{e(label(status))}</span><h3><a href='{e(safe_url)}' target='_blank' rel='noopener noreferrer'>{e(source['title'])}</a></h3><p>{e(source.get('summary', ''))}</p><small>{e(source.get('architecture', ''))} · {e(source.get('license', ''))}</small><div class='links'>")
        if source.get("cached_path"):
            parts.append(f"<a href='{e(file_url(store.config.root / source['cached_path']))}'>缓存工作流</a>")
        parts.append(f"</div><details><summary>依赖与来源</summary><pre>{e(json.dumps({k:v for k,v in source.items() if k in ('required_nodes','required_models','revision','checked_at','validation','runtime_jobs')}, ensure_ascii=False, indent=2))}</pre></details></article>")
    parts.append("</div></section><section id='models'><h2>本地模型</h2><div class='card'><table><tr><th>模型</th><th>类型</th><th>占用</th><th>状态</th></tr>")
    for asset in assets:
        state = '文件无效' if asset.get('file_validation', {}).get('status') == 'invalid' else '已登记' if asset.get('available') else '文件已移除'
        parts.append(f"<tr><td>{e(asset['name'])}</td><td>{e(asset['category'])}</td><td>{asset['bytes']/1e9:.2f} GB</td><td>{state}</td></tr>")
    parts.append("</table></div><h3>系列下载预算</h3><div class='grid'>")
    for item in series:
        budget = store.budget(item["id"])
        parts.append(f"<div class='card'><h3>{e(item['id'])} · {e(item['name'])}</h3><p>{e(item.get('style_key') or '尚未绑定风格')}</p><p>累计新增 {budget['used']/1e9:.2f} / {budget['limit']/1e9:.0f} GB<br>下载预留 {budget['reserved']/1e9:.2f} GB</p></div>")
    parts.append("</div></section><section id='materials'><h2>输入素材</h2><div class='grid'>")
    for material in store.all("materials"):
        parts.append(f"<div class='card'><h3>{e(material['name'])}</h3><p>{e(material['role'])} · {e(material['kind'])}</p><a href='{e(file_url(material['path']))}'>本地副本</a>")
        if material.get("text_path"):
            parts.append(f" · <a href='{e(file_url(material['text_path']))}'>提取文本</a>")
        if material.get("visual_pages"):
            parts.append(f"<p>页面预览 {len(material['visual_pages'])} 页；未渲染 {len(material.get('unrendered_pages', []))} 页</p>")
            parts.append("<div class='links'>" + "".join(f"<a href='{e(file_url(x['path']))}'>第{x['page']}页</a>" for x in material['visual_pages']) + "</div>")
        if material.get("embedded_images"):
            parts.append("<div class='links'>" + "".join(f"<a href='{e(file_url(x))}'>嵌入图片 {i+1}</a>" for i,x in enumerate(material['embedded_images'])) + "</div>")
        parts.append("</div>")
    parts.append("</div></section></main><script>document.getElementById('search').addEventListener('input',e=>{let q=e.target.value.toLowerCase().trim();document.querySelectorAll('.source').forEach(c=>c.hidden=!c.dataset.search.includes(q))});</script></html>")
    return "".join(parts)


def allowed_file(config, path):
    return any(within(path, root) for root in [config.data / x for x in ("runs", "materials", "library", "styles")] + [config.root / "comfy_workflow/output"])


def serve(config, port=8191):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/file":
                path = Path(parse_qs(parsed.query).get("p", [""])[0]).resolve()
                if not allowed_file(config, path) or not path.is_file():
                    self.send_error(404)
                    return
                typ = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                if path.suffix.lower() in (".html", ".js", ".svg"):
                    typ = "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", typ)
                self.send_header("Content-Length", str(path.stat().st_size))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with path.open("rb") as stream:
                    import shutil
                    shutil.copyfileobj(stream, self.wfile)
                return
            if parsed.path not in ("/", "/api/summary"):
                self.send_error(404)
                return
            db = Store(config)
            try:
                if parsed.path == "/api/summary":
                    data = json.dumps({x: len(db.all(x)) for x in ("styles", "series", "jobs", "sources", "assets", "materials")}).encode()
                    typ = "application/json"
                else:
                    data, typ = render(db).encode("utf-8"), "text/html; charset=utf-8"
            finally:
                db.db.close()
            self.send_response(200)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass
    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    try:
        server = LocalServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        raise SeriesError("browser_bind_failed", "资料页端口不可用，请先关闭旧实例或选择其他端口", {"port": port, "error": str(exc)}) from exc
    print(json.dumps({"ok": True, "url": f"http://127.0.0.1:{server.server_port}/", "read_only": True}), flush=True)
    server.serve_forever()
