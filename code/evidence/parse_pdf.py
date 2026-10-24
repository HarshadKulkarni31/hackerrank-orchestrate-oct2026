"""Parser for PDF evidence documents using pure Python standard library."""

import base64
import re
import zlib
from pathlib import Path
from typing import List, Dict, Any, Optional


def parse_pdf_document(pdf_path: Path) -> List[str]:
    """Extracts text chunks from PDF streams compressed with ASCII85 and Flate."""
    if not pdf_path.exists():
        return []

    with open(pdf_path, "rb") as f:
        data = f.read()

    text_chunks: List[str] = []
    idx = 0
    while True:
        pos = data.find(b"stream", idx)
        if pos == -1:
            break
        end = data.find(b"endstream", pos)
        if end == -1:
            break
        stream_data = data[pos + 6 : end].strip()
        idx = end + 9

        # Attempt decoding
        try:
            clean = b"".join(stream_data.split())
            if not clean.startswith(b"<~"):
                clean = b"<~" + clean
            if not clean.endswith(b"~>"):
                clean = clean + b"~>"
            decomp = zlib.decompress(base64.a85decode(clean, adobe=True))
            matches = re.findall(
                r"\(([^\)]+)\)\s*Tj", decomp.decode("latin-1", errors="ignore")
            )
            if matches:
                text_chunks.extend(matches)
        except Exception:
            # Fallback to direct zlib decompression if not ASCII85
            try:
                decomp = zlib.decompress(stream_data)
                matches = re.findall(
                    r"\(([^\)]+)\)\s*Tj", decomp.decode("latin-1", errors="ignore")
                )
                if matches:
                    text_chunks.extend(matches)
            except Exception:
                pass

    return text_chunks
