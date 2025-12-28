"""
Schema extraction module for PDF form fields.

This module extracts field schemas from fillable PDFs, combining metadata
from pypdf (labels, types) with spatial information from PyMuPDF (bounding boxes).
"""

import re
import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from pypdf import PdfReader
import fitz  # PyMuPDF


class SchemaExtractor:
    """Extracts and normalizes form field schemas from fillable PDFs."""
    
    def __init__(self):
        self.used_keys = set()
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to a normalized slug (lowercase, underscores, no special chars)."""
        text = text.strip().lower()
        text = re.sub(r"[''']", "", text)  # Remove apostrophes
        text = re.sub(r"[^a-z0-9]+", "_", text)  # Replace non-alphanumeric with underscore
        text = re.sub(r"_+", "_", text).strip("_")  # Collapse multiple underscores
        return text or "field"
    
    @staticmethod
    def pdf_type_to_type(ft: str) -> str:
        """Convert PDF field type to our type string."""
        return {
            "/Tx": "text",
            "/Btn": "button",
            "/Ch": "choice",
            "/Sig": "signature",
        }.get((ft or "").strip(), "unknown")
    
    @staticmethod
    def is_parent_field(pdf_name: str, label: str, ft: str, bbox: Optional[list]) -> bool:
        """Check if this is a parent/group field that should be filtered out."""
        # Parent/group fields usually have:
        # - no label
        # - no /FT
        # - no bbox
        if bbox is not None:
            return False
        if (label or "").strip():
            return False
        if (ft or "").strip():
            return False
        # Often exactly a prefix like "APS1" or "APS2"
        return "." not in pdf_name
    
    def unique_key(self, base: str) -> str:
        """Ensure key is unique by appending number if needed."""
        if base not in self.used_keys:
            self.used_keys.add(base)
            return base
        i = 2
        while f"{base}_{i}" in self.used_keys:
            i += 1
        key = f"{base}_{i}"
        self.used_keys.add(key)
        return key
    
    @staticmethod
    def detect_date_part(pdf_name: str) -> Optional[Tuple[str, str]]:
        """Detect if field is part of a date (day/month/year)."""
        # e.g. APS1.Date_of_birth_d
        m = re.search(r"(date[_ ]?[a-z0-9]+)[_. ]([dmy])\b", pdf_name, re.IGNORECASE)
        if not m:
            return None
        date_key = SchemaExtractor.slugify(m.group(1))
        part = {"d": "day", "m": "month", "y": "year"}[m.group(2).lower()]
        return date_key, part
    
    @staticmethod
    def detect_phone_part(label: str, pdf_name: str) -> Optional[Tuple[str, str]]:
        """Detect if field is part of a phone number."""
        t = (label or pdf_name).lower()
        # group
        if "home phone" in t:
            group = "home_phone"
        elif "cell phone" in t or "mobile phone" in t:
            group = "cell_phone"
        elif "work phone" in t:
            group = "work_phone"
        else:
            return None
        
        # part
        if "area code" in t:
            part = "area_code"
        elif "first three" in t or "first 3" in t:
            part = "first3"
        elif "last four" in t or "last 4" in t:
            part = "last4"
        else:
            part = "full"
        
        return group, part
    
    @staticmethod
    def detect_repeated_medication(pdf_name: str) -> Optional[Tuple[str, str]]:
        """Detect if field is part of a medication entry (name/dose/often)."""
        # Medication1, Dose1, Often1...
        m = re.search(r"\b(medication|dose|often)\s*([0-9]+)\b", pdf_name, re.IGNORECASE)
        if not m:
            return None
        part = SchemaExtractor.slugify(m.group(1))
        idx = int(m.group(2))
        group = f"medication_{idx}"
        # name medication field as medication_{i}_name for clarity
        if part == "medication":
            part = "name"
        return group, part
    
    def extract_schema(self, pdf_path: str, filter_clear_button: bool = True) -> Dict[str, Any]:
        """
        Extract schema from fillable PDF.
        
        Args:
            pdf_path: Path to fillable PDF file
            filter_clear_button: If True, filter out "Clear Form" button field
            
        Returns:
            Dictionary mapping normalized field names to field metadata
        """
        # Reset used keys for new extraction
        self.used_keys = set()
        
        # 1) pypdf: labels + /FT types
        reader = PdfReader(pdf_path)
        pfields = reader.get_fields() or {}
        
        meta = {}
        for name, d in pfields.items():
            meta[name] = {
                "label": (d.get("/TU") or "").strip(),
                "ft": (d.get("/FT") or "").strip(),
            }
        
        # 2) PyMuPDF: bbox + page
        doc = fitz.open(pdf_path)
        widgets = {}
        for pno in range(doc.page_count):
            page = doc[pno]
            for w in (page.widgets() or []):
                fname = (w.field_name or "").strip()
                if not fname:
                    continue
                r = w.rect
                bbox = [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]
                # if multiple widgets share name, keep first (or store list)
                widgets.setdefault(fname, {"page": pno, "bbox": bbox})
        
        # 3) merge + normalize into required output shape
        out: Dict[str, Any] = {}
        
        all_names = sorted(set(meta.keys()) | set(widgets.keys()))
        for pdf_name in all_names:
            label = meta.get(pdf_name, {}).get("label", "")
            ft = meta.get(pdf_name, {}).get("ft", "")
            bbox = widgets.get(pdf_name, {}).get("bbox")
            page = widgets.get(pdf_name, {}).get("page")
            
            # Filter "Clear Form" button if requested
            if filter_clear_button and "Button" in pdf_name and "Clear" in label:
                continue
            
            # filter parent/group fields
            if self.is_parent_field(pdf_name, label, ft, bbox):
                continue
            
            # Determine base normalized name
            # Prefer label, otherwise last segment of pdf_name
            base = label if label else pdf_name.split(".")[-1]
            base_norm = self.slugify(base)
            
            group = None
            part = None
            
            # Grouping rules (override base_norm for better consistency)
            phone = self.detect_phone_part(label, pdf_name)
            if phone:
                group, part = phone
                base_norm = f"{group}_{part}"
            
            date = self.detect_date_part(pdf_name)
            if date:
                group, part = date
                base_norm = f"{group}_{part}"
            
            med = self.detect_repeated_medication(pdf_name)
            if med:
                group, part = med
                base_norm = f"{group}_{part}"
            
            key = self.unique_key(base_norm)
            
            out[key] = {
                "label": label or pdf_name,
                "type": self.pdf_type_to_type(ft),
                "bbox": bbox,               # required
                "normalized_name": key,     # required
                "pdf_name": pdf_name,
                "page": page,
                "group": group,
                "part": part,
            }
        
        return out


def extract_schema(pdf_path: str, output_path: Optional[str] = None, 
                   filter_clear_button: bool = True) -> Dict[str, Any]:
    """
    Convenience function to extract schema and optionally save to JSON.
    
    Args:
        pdf_path: Path to fillable PDF file
        output_path: Optional path to save schema JSON. If None, schema is not saved.
        filter_clear_button: If True, filter out "Clear Form" button field
        
    Returns:
        Dictionary mapping normalized field names to field metadata
    """
    extractor = SchemaExtractor()
    schema = extractor.extract_schema(pdf_path, filter_clear_button=filter_clear_button)
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)
    
    return schema

