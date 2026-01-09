from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import re


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_text_from_docx(file_path: Path) -> str:
    from docx import Document

    doc = Document(file_path)
    parts: List[str] = []
    for paragraph in doc.paragraphs:
        txt = (paragraph.text or "").strip()
        if txt:
            parts.append(txt)
    return "\n\n".join(parts)


def extract_text_from_pdf(file_path: Path) -> str:
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    parts: List[str] = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        txt = txt.strip()
        if txt:
            parts.append(txt)
    return "\n\n".join(parts)


def extract_text_from_xlsx(file_path: Path) -> str:
    import pandas as pd

    excel_file = pd.ExcelFile(file_path)
    parts: List[str] = []
    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        parts.append(f"=== Planilha: {sheet_name} ===")
        parts.append(df.to_string(index=False))
        parts.append("")
    return "\n".join(parts).strip()


def extract_text_from_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore").strip()


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return extract_text_from_docx(file_path)
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    if suffix in {".xlsx", ".xls"}:
        return extract_text_from_xlsx(file_path)
    if suffix in {".txt", ".md"}:
        return extract_text_from_txt(file_path)
    return ""


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 300) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    last_start: Optional[int] = None

    while start < len(text):
        end = min(len(text), start + chunk_size)
        window = text[start:end]

        if end < len(text):
            search_start = int(len(window) * 0.6)
            candidates = [
                window.rfind("\n\n", search_start),
                window.rfind("\n", search_start),
                window.rfind(". ", search_start),
                window.rfind("; ", search_start),
            ]
            cut = max(candidates)
            if cut != -1:
                end = start + cut + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        next_start = max(0, end - overlap)
        if last_start is not None and next_start <= last_start:
            next_start = end
        last_start = start
        start = next_start

    return chunks


def list_files(root_dir: Path, recursive: bool = True) -> List[Path]:
    if not root_dir.exists():
        return []
    if root_dir.is_file():
        return [root_dir]
    if recursive:
        return [p for p in root_dir.rglob("*") if p.is_file()]
    return [p for p in root_dir.iterdir() if p.is_file()]


def relative_source(root_dir: Path, file_path: Path) -> str:
    try:
        return str(file_path.relative_to(root_dir)).replace("\\", "/")
    except Exception:
        return file_path.name

