"""Extract bounded local text and basic metadata from common document formats."""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

_MAX_SIZE = 25 * 1024 * 1024

class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.parts: list[str] = []; self.title: str | None = None; self._in_title = False
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._in_title = tag.lower() == "title"
    def handle_endtag(self, tag: str) -> None:
        self._in_title = False
    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        if self._in_title: self.title = (self.title or "") + data


def _xml_text(archive: zipfile.ZipFile, names: list[str]) -> str:
    values: list[str] = []
    for name in names:
        try: root = ElementTree.fromstring(archive.read(name))
        except (KeyError, ElementTree.ParseError): continue
        values.extend(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    return "\n".join(value for value in values if value)


def _ooxml_metadata(archive: zipfile.ZipFile) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try: root = ElementTree.fromstring(archive.read("docProps/core.xml"))
    except (KeyError, ElementTree.ParseError): return result
    for node in root:
        key = node.tag.rsplit("}", 1)[-1]
        if key in {"title", "creator", "created", "modified"} and node.text: result[key] = node.text
    return result


def _extract_xlsx(archive: zipfile.ZipFile) -> str:
    shared = _xml_text(archive, ["xl/sharedStrings.xml"]).splitlines()
    values: list[str] = []
    for name in sorted(item for item in archive.namelist() if item.startswith("xl/worksheets/") and item.endswith(".xml")):
        try: root = ElementTree.fromstring(archive.read(name))
        except ElementTree.ParseError: continue
        cells: list[str] = []
        for cell in root.iter():
            if not cell.tag.endswith("}c"): continue
            value = next((node.text for node in cell.iter() if node.tag.endswith("}v")), "")
            if cell.attrib.get("t") == "s" and value and value.isdigit() and int(value) < len(shared): value = shared[int(value)]
            cells.append(value or "")
        if cells: values.append("\t".join(cells))
    return "\n".join(values)


def run(args: dict[str, Any]) -> dict[str, Any]:
    value = args.get("path")
    if not isinstance(value, str) or not value: raise ValueError("'path' is required")
    path = Path(value).expanduser().resolve()
    if not path.is_file(): raise ValueError(f"File does not exist: {path}")
    if path.stat().st_size > _MAX_SIZE: raise ValueError("File exceeds the 25 MB extraction limit")
    max_chars = min(max(int(args.get("max_chars", 20_000)), 1), 100_000)
    max_pages = min(max(int(args.get("max_pages", 10)), 1), 100)
    suffix = path.suffix.lower(); metadata: dict[str, Any] = {"format": suffix.lstrip("."), "size_bytes": path.stat().st_size}; text = ""
    if suffix == ".pdf":
        executable = shutil.which("pdftotext")
        if not executable: raise ValueError("PDF extraction requires the local 'pdftotext' command")
        result = subprocess.run([executable, "-f", "1", "-l", str(max_pages), str(path), "-"], capture_output=True, text=True, timeout=20, check=False)
        if result.returncode: raise ValueError("pdftotext could not extract this PDF")
        text = result.stdout; metadata["max_pages"] = max_pages
    elif suffix in {".docx", ".xlsx", ".pptx"}:
        try:
            with zipfile.ZipFile(path) as archive:
                metadata.update(_ooxml_metadata(archive))
                if suffix == ".docx": text = _xml_text(archive, ["word/document.xml"])
                elif suffix == ".pptx": text = _xml_text(archive, sorted(item for item in archive.namelist() if item.startswith("ppt/slides/slide") and item.endswith(".xml")))
                else: text = _extract_xlsx(archive)
        except zipfile.BadZipFile as error: raise ValueError("Office document is not a valid OOXML archive") from error
    elif suffix in {".html", ".htm"}:
        parser = _HTMLText(); parser.feed(path.read_text(encoding="utf-8", errors="replace")); text = "\n".join(parser.parts); metadata["title"] = parser.title
    elif suffix in {".md", ".markdown", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        if suffix != ".txt": text = re.sub(r"!?(\[[^\]]*\])\([^)]*\)", r"\1", text); text = re.sub(r"^[#>*`]+\s?", "", text, flags=re.MULTILINE)
    else: raise ValueError("Supported formats: PDF, DOCX, XLSX, PPTX, HTML, Markdown, TXT")
    text = html.unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()
    return {"read_only": True, "metadata": metadata, "text": text[:max_chars], "truncated": len(text) > max_chars}
