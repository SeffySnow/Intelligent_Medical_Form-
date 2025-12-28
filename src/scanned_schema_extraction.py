"""
Scanned form schema extraction (OCR + layout parsing).

This module is intentionally NOT used by main.ipynb by default.
Rationale:
- For fillable PDFs, `src/schema_extraction.py` uses AcroForm metadata which is more reliable.
- For scanned/non-fillable PDFs (e.g., `form_scanned.pdf`), this provides a best-effort fallback
  using OCR + simple layout heuristics to propose field bboxes and labels.

Output shape matches `schema_extraction.extract_schema` (normalized_key -> metadata dict).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OcrWord:
    text: str
    bbox: Tuple[float, float, float, float]  # x0,y0,x1,y1 in image coords


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[’']", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "field"


def _unique_key(base: str, used: set[str]) -> str:
    if base not in used:
        used.add(base)
        return base
    i = 2
    while f"{base}_{i}" in used:
        i += 1
    key = f"{base}_{i}"
    used.add(key)
    return key


def _render_pdf_page_to_image(pdf_path: str, page_index: int = 0, dpi: int = 200):
    import fitz  # PyMuPDF
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return img


def _ocr_words(image) -> List[OcrWord]:
    """
    OCR words with bounding boxes using pytesseract.
    """
    try:
        import pytesseract
        from pytesseract import Output
    except Exception as e:
        raise ImportError(
            "pytesseract is required for scanned schema extraction. "
            "Install Python deps via `pip install -r requirements.txt` and ensure the "
            "Tesseract binary is installed on your system."
        ) from e

    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    words: List[OcrWord] = []
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(OcrWord(txt, (float(x), float(y), float(x + w), float(y + h))))
    return words


def _detect_input_lines(image) -> List[Tuple[float, float, float, float]]:
    """
    Detect likely input 'lines' / boxes using simple morphology on a binarized image.
    Returns bboxes in image coordinates.

    Heuristic:
    - Find long horizontal contours (underscores/lines) that are likely fill areas.
    - Treat each long horizontal contour as a field bbox.
    """
    import cv2
    import numpy as np

    img = np.array(image)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # binary inverse (lines/ink -> white)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # emphasize horizontal structures
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: List[Tuple[float, float, float, float]] = []
    h, w = gray.shape
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        # filter tiny/noisy contours
        if cw < 120 or ch > 20:
            continue
        # avoid page borders
        if x < 5 or (x + cw) > (w - 5):
            # still allow, but many forms have full-width lines; keep it.
            pass
        boxes.append((float(x), float(y), float(x + cw), float(y + ch)))

    # Sort top-to-bottom, left-to-right
    boxes.sort(key=lambda b: (b[1], b[0]))
    return boxes


def _find_label_for_box(words: List[OcrWord], box: Tuple[float, float, float, float]) -> str:
    """
    Find a label for a detected field box by looking for words to the left of the box
    on the same horizontal band, and/or slightly above.
    """
    x0, y0, x1, y1 = box
    cy = (y0 + y1) / 2.0

    # candidates: words with centers left of box and vertically aligned
    aligned: List[Tuple[float, str]] = []
    for w in words:
        wx0, wy0, wx1, wy1 = w.bbox
        wcy = (wy0 + wy1) / 2.0
        wcx = (wx0 + wx1) / 2.0
        if wcx < x0 and abs(wcy - cy) < 18:
            # score by closeness to box's left edge
            aligned.append((x0 - wx1, w.text))

    aligned.sort(key=lambda t: t[0])
    label = " ".join([t[1] for t in aligned[:8]]).strip()

    # fallback: look above
    if not label:
        above: List[Tuple[float, str]] = []
        for w in words:
            wx0, wy0, wx1, wy1 = w.bbox
            if wy1 < y0 and (x0 - 40) <= wx0 <= (x1 + 40) and (y0 - wy1) < 35:
                above.append((y0 - wy1, w.text))
        above.sort(key=lambda t: t[0])
        label = " ".join([t[1] for t in above[:10]]).strip()

    return label or "Unknown Field"


def extract_scanned_schema(
    pdf_path: str,
    output_path: Optional[str] = None,
    page_index: int = 0,
    dpi: int = 200,
) -> Dict[str, Any]:
    """
    Best-effort schema extraction for scanned/non-fillable PDFs.

    Returns a dict keyed by normalized_name, with:
      - label
      - type: "text"
      - bbox: [x0,y0,x1,y1]
      - normalized_name
      - pdf_name: None (no AcroForm fields)
      - page
    """
    used = set()
    image = _render_pdf_page_to_image(pdf_path, page_index=page_index, dpi=dpi)
    words = _ocr_words(image)
    boxes = _detect_input_lines(image)

    out: Dict[str, Any] = {}
    for box in boxes:
        label = _find_label_for_box(words, box)
        base = _slugify(label)
        key = _unique_key(base, used)
        out[key] = {
            "label": label,
            "type": "text",
            "bbox": [float(box[0]), float(box[1]), float(box[2]), float(box[3])],
            "normalized_name": key,
            "pdf_name": None,
            "page": page_index,
            "group": None,
            "part": None,
        }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

    return out


