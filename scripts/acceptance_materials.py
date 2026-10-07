"""Persistent input fixtures for integration acceptance, not production briefs."""
from pathlib import Path
import json
import zipfile

import pymupdf
from PIL import Image, ImageDraw
from comfy_series.common import Config, Store, now, write_json
from comfy_series.ingest import ingest


def main():
    config = Config()
    folder = config.data / "acceptance" / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    text = "Acceptance fixture: an empty underground communications room.\nSteel console, cold white lights, central wide screen.\nSize: 1001 x 733. PNG. Avoid people, readable text and watermarks.\n"
    (folder / "brief.md").write_text(text, encoding="utf-8")
    # A scanned page deliberately contains no PDF text layer.
    page_image = Image.new("RGB", (900, 550), "white")
    ImageDraw.Draw(page_image).multiline_text((35, 45), text, fill="black", font_size=24, spacing=14)
    scan = folder / "scan.png"
    page_image.save(scan)
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=550)
    page.insert_image(page.rect, filename=str(scan))
    doc.save(folder / "scanned-brief.pdf")
    doc.close()
    with zipfile.ZipFile(folder / "brief.docx", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        paragraphs = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines())
        archive.writestr("word/document.xml", f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>')
        archive.writestr("word/media/reference.png", scan.read_bytes())
    db = Store(config)
    try:
        materials = [ingest(db, str(folder / name), "context") for name in ("brief.md", "scanned-brief.pdf", "brief.docx")]
        # Read only the public official example page; preserve its copied contents.
        try:
            materials.append(ingest(db, "https://comfyanonymous.github.io/ComfyUI_examples/sdxl/", "context"))
            url_status = "read"
        except Exception as exc:
            url_status = {"status": "unreadable", "code": getattr(exc, "code", type(exc).__name__)}
        record = {"at": now(), "purpose": "synthetic input acceptance fixtures, not a production generation request", "materials": materials,
                  "url_status": url_status, "visual_review": "pending", "brief": {"subject": "empty underground communications room", "composition": "central steel console and wide screen", "lighting": "cold white lights", "output": {"width":1001,"height":733,"format":"PNG"}, "avoid":["people","readable text","watermarks"]}}
        write_json(config.data / "acceptance/material-inputs.json", record)
        print(json.dumps({"materials": [{"id": x["id"], "kind": x["kind"], "visual_pages": x.get("visual_pages", []), "embedded_images": x.get("embedded_images", [])} for x in materials], "url_status": url_status}))
    finally:
        db.db.close()


if __name__ == "__main__":
    main()
