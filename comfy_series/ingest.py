from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree
import httpx
import pymupdf
from PIL import Image
from .common import SeriesError, digest, now, write_json, external_http


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip, self.text = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "br", "h1", "h2", "li"):
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def ingest(store, source, role="context", pages=None, text=None):
    if role not in ("style", "subject", "composition", "structure", "context"):
        raise SeriesError("reference_role", "素材用途无效")
    parsed = urlparse(source)
    is_url = parsed.scheme in ("http", "https")
    if parsed.username or parsed.password:
        raise SeriesError("url_credentials", "网址不得含认证信息")
    content = None
    if text is not None:
        content = text.encode("utf-8")
        key = "M-" + hashlib.sha256(content).hexdigest()[:16]
        name, kind = "note.txt", "text"
    elif is_url:
        name, kind = "page.html", "url"
        try:
            with external_http(store.config, source, follow_redirects=True, timeout=30) as client:
                response = client.get(source)
                response.raise_for_status()
                if len(response.content) > 20_000_000:
                    raise SeriesError("material_too_large", "网页内容过大；请提供文档文件或选定内容")
                content = response.content
                key = "M-" + hashlib.sha256(source.encode() + content).hexdigest()[:16]
        except httpx.HTTPError as exc:
            raise SeriesError("material_unavailable", "网页无法读取，可由Codex浏览后将来源摘要作为素材导入", {"url": source}) from exc
    else:
        path = Path(source).resolve()
        if not path.is_file():
            raise SeriesError("material_missing", "素材文件不存在", {"path": str(path)})
        key = "M-" + digest(path)[:16]
        name, kind = path.name, path.suffix.lower().lstrip(".")
    folder = store.config.data / "materials" / key
    folder.mkdir(parents=True, exist_ok=True)
    copy = folder / name
    if content is not None:
        copy.write_bytes(content)
    elif not copy.exists():
        shutil.copy2(path, copy)
    entry = {"id": key, "source": source, "path": str(copy.resolve()), "name": name, "kind": kind,
             "role": role, "sha256": digest(copy), "created_at": now(), "visual_pages": [], "embedded_images": []}
    extracted = ""
    if kind in ("png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"):
        with Image.open(copy) as im:
            im.verify()
        with Image.open(copy) as im:
            entry["image_size"] = [im.width, im.height]
            entry["image_format"] = im.format
        entry["kind"] = "image"
    elif kind in ("txt", "md", "markdown", "text"):
        try:
            extracted = copy.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            extracted = copy.read_text(encoding="gb18030")
    elif kind == "url":
        parser = PageText()
        parser.feed(content.decode("utf-8", errors="replace"))
        extracted = re.sub(r"\n\s*\n+", "\n\n", "".join(parser.text)).strip()
    elif kind == "pdf":
        with pymupdf.open(copy) as document:
            if document.is_encrypted:
                raise SeriesError("document_encrypted", "PDF需要密码；请提供可读取版本")
            entry["page_count"] = len(document)
            selected = set(pages or range(1, min(len(document), 20) + 1))
            if any(type(x) is not int or not 1 <= x <= len(document) for x in selected):
                raise SeriesError("invalid_pages", "PDF页码不在文档范围内")
            texts = []
            for i, page in enumerate(document, 1):
                page_text = page.get_text().strip()
                texts.append(f"\n--- Page {i} ---\n{page_text}")
                # Render selected pages even when there is text: figures may carry important requirements.
                if i in selected:
                    output = folder / f"page_{i:04d}.png"
                    page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25), alpha=False).save(output)
                    entry["visual_pages"].append({"page": i, "path": str(output), "has_text": bool(page_text)})
            extracted = "\n".join(texts)
            entry["unrendered_pages"] = sorted(set(range(1, len(document) + 1)) - selected)
            entry["needs_visual_reading"] = [x["page"] for x in entry["visual_pages"] if not x["has_text"]]
    elif kind == "docx":
        with zipfile.ZipFile(copy) as archive:
            texts = []
            for item in archive.namelist():
                if re.fullmatch(r"word/(document|header\d+|footer\d+|footnotes|endnotes)\.xml", item):
                    tree = ElementTree.fromstring(archive.read(item))
                    texts.extend("".join(x.itertext()) for x in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
                elif item.startswith("word/media/") and not item.endswith("/"):
                    output = folder / ("embedded_" + Path(item).name)
                    output.write_bytes(archive.read(item))
                    entry["embedded_images"].append(str(output))
            extracted = "\n".join(texts)
    else:
        raise SeriesError("unsupported_material", "第一版支持图片、TXT/MD/PDF/DOCX和网页")
    if extracted:
        text_path = folder / "extracted.txt"
        text_path.write_text(extracted, encoding="utf-8")
        entry["text_path"] = str(text_path)
        entry["text_chars"] = len(extracted)
    old = store.get("materials", key)
    entry["sources"] = sorted(set((old or {}).get("sources", [(old or {}).get("source", source)]) + [source]))
    entry["roles"] = sorted(set((old or {}).get("roles", [(old or {}).get("role", role)]) + [role]))
    if old and old.get("sha256") == entry["sha256"]:
        entry["created_at"] = old["created_at"]
        if kind == "pdf":
            known = {x["page"]:x for x in old.get("visual_pages", [])}
            known.update({x["page"]:x for x in entry["visual_pages"]})
            entry["visual_pages"] = [known[x] for x in sorted(known)]
            entry["unrendered_pages"] = sorted(set(range(1, entry["page_count"]+1))-set(known))
            entry["needs_visual_reading"] = [x["page"] for x in entry["visual_pages"] if not x["has_text"]]
    write_json(folder / "material.json", entry)
    store.put("materials", key, entry)
    return entry
