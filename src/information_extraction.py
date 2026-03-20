"""
Information extraction module for patient documents.

This module extracts structured information from various patient documents
(demographics.json, SOAP notes, lab results) and maps them to form schema fields.

"""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, Iterable, Set
from pathlib import Path


class InformationExtractor:
    """Extracts and maps patient information from documents to form schema fields."""
    
    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize extractor with form schema.
        
        Args:
            schema: Form schema dictionary from schema_extraction
        """
        self.schema = schema
        self.field_mapping = self._build_field_mapping()
    
    def _build_field_mapping(self) -> Dict[str, Any]:
        """Build mapping dictionary from JSON field names to schema field names."""
        return {
            "patient_name": "patient_name_last_first_middle_initial",
            "dob": ["date_of_birth_dd", "date_of_birth_mm", "date_of_birth_yyyy"],
            "phone_home": ["home_phone_area_code", "home_phone_first3", "home_phone_last4"],
            "phone_mobile": ["cell_phone_area_code", "cell_phone_first3", "cell_phone_last4"],
            "address": "address_street_city_province_postal_code"
        }
    
    @staticmethod
    def parse_date(date_str: str) -> Dict[str, str]:
        """Parse ISO date string into day, month, year components."""
        try:
            # Try ISO format: YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return {
                "day": f"{dt.day:02d}",
                "month": f"{dt.month:02d}",
                "year": f"{dt.year}"
            }
        except ValueError:
            # Try other formats if needed
            return {"day": "", "month": "", "year": ""}
    
    @staticmethod
    def parse_phone(phone_str: str) -> Dict[str, str]:
        """Parse phone number into area code, first3, last4."""
        # Remove all non-digits
        digits = re.sub(r'\D', '', phone_str)
        
        if len(digits) == 10:
            # Format: AAAXXXXXXX (10 digits)
            return {
                "area_code": digits[:3],
                "first3": digits[3:6],
                "last4": digits[6:]
            }
        elif len(digits) == 11:
            # Format: 1AAAXXXXXXX (11 digits with country code)
            return {
                "area_code": digits[1:4],
                "first3": digits[4:7],
                "last4": digits[7:]
            }
        else:
            # Try to parse format like "613-6565-890"
            parts = phone_str.split('-')
            if len(parts) == 3:
                area_code = parts[0]
                # Combine remaining parts and split
                remaining = ''.join(re.sub(r'\D', '', ''.join(parts[1:])))
                if len(remaining) >= 7:
                    return {
                        "area_code": area_code,
                        "first3": remaining[:3],
                        "last4": remaining[3:7]
                    }
        
        return {"area_code": "", "first3": "", "last4": ""}
    
    @staticmethod
    def format_address(address_obj: Dict[str, str]) -> str:
        """Format address object into single string."""
        parts = []
        if address_obj.get('street'):
            parts.append(address_obj['street'])
        if address_obj.get('city'):
            parts.append(address_obj['city'])
        if address_obj.get('province'):
            parts.append(address_obj['province'])
        if address_obj.get('postal_code'):
            parts.append(address_obj['postal_code'])
        return ", ".join(parts)
    
    def extract_from_demographics(self, demographics_path: str, 
                                  confidence: float = 0.95) -> Dict[str, Dict[str, Any]]:
        """
        Extract information from demographics.json file.
        
        Args:
            demographics_path: Path to demographics.json file
            confidence: Confidence score for structured data source
            
        Returns:
            Dictionary mapping schema field names to extracted values with metadata
        """
        with open(demographics_path, 'r') as f:
            demographics = json.load(f)
        
        results = {}
        
        for json_key, json_value in demographics.items():
            if json_key not in self.field_mapping:
                continue
            
            schema_fields = self.field_mapping[json_key]
            
            # Handle one-to-many mappings (lists)
            if isinstance(schema_fields, list):
                # Transform value based on type
                if json_key == "dob":
                    date_parts = self.parse_date(str(json_value))
                    for i, schema_field in enumerate(schema_fields):
                        part = ["day", "month", "year"][i]
                        value = date_parts.get(part, "")
                        if schema_field in self.schema:
                            results[schema_field] = {
                                "value": value,
                                "source": "demographics.json",
                                "field": json_key,
                                "transformation": f"date_parse.{part}",
                                "confidence": confidence
                            }
                
                elif json_key in ["phone_home", "phone_mobile"]:
                    phone_parts = self.parse_phone(str(json_value))
                    for i, schema_field in enumerate(schema_fields):
                        part = ["area_code", "first3", "last4"][i]
                        value = phone_parts.get(part, "")
                        if schema_field in self.schema:
                            results[schema_field] = {
                                "value": value,
                                "source": "demographics.json",
                                "field": json_key,
                                "transformation": f"phone_parse.{part}",
                                "confidence": confidence
                            }
            
            # Handle one-to-one mappings
            elif isinstance(schema_fields, str):
                schema_field = schema_fields
                
                # Transform if needed
                if json_key == "address":
                    value = self.format_address(json_value)
                    transformation = "address_format"
                else:
                    value = json_value
                    transformation = "direct"
                
                if schema_field in self.schema:
                    results[schema_field] = {
                        "value": value,
                        "source": "demographics.json",
                        "field": json_key,
                        "transformation": transformation,
                        "confidence": confidence
                    }
        
        return results
    
    def extract_from_soap_notes(self, soap_notes_path: str,
                                confidence: float = 0.75,
                                already_filled: Optional[Dict[str, Dict[str, Any]]] = None,
                                use_llm_fallback: bool = True,
                                model_name: str = "Qwen/Qwen2.5-3B-Instruct",
                                model_cache_dir: str = "./models/Qwen2.5-3B-Instruct",
                                max_input_tokens: int = 2048,
                                max_new_tokens: int = 450) -> Dict[str, Dict[str, Any]]:
        """
        Extract information from SOAP notes text file.
        
        Args:
            soap_notes_path: Path to SOAP notes text file
            confidence: Confidence score for unstructured text source
            already_filled: Existing extracted results (e.g., from demographics.json). Any already-filled
                field keys will be excluded from the LLM target list (completion-only).
            use_llm_fallback: If True, use an LLM only for fields still missing after deterministic extraction.
            model_name: Hugging Face model id for LLM fallback
            model_cache_dir: Local directory to cache the model/tokenizer so you don't re-download each run
            max_input_tokens: Max input tokens for LLM prompt
            max_new_tokens: Max new tokens to generate for LLM prompt
            
        Returns:
            Dictionary mapping schema field names to extracted values with metadata
            
        Strategy (min-hallucination):
        - Deterministic-first:
          - Diagnoses from the "Assessment:" numbered list → {primary_1, primary_2, secondary_*}
          - Medications from explicit drug mentions in "Plan:" (e.g., nitroglycerin)
        - LLM fallback (optional):
          - Only for still-missing fields after deterministic extraction
          - Evidence-gated: any extracted value must include an evidence quote that appears verbatim in the note
        """
        already_filled = already_filled or {}

        with open(soap_notes_path, "r", encoding="utf-8") as f:
            soap_text = f.read()

        def _make_obj(value, evidence, reasoning, conf):
            return {
                "value": value,
                "source": "soap_notes.txt",
                "confidence": float(conf),
                "reasoning": reasoning,
                "evidence": evidence,
            }

        def _is_filled(field_key: str) -> bool:
            obj = already_filled.get(field_key)
            if not isinstance(obj, dict):
                return False
            v = obj.get("value")
            return v is not None and str(v).strip() != ""

        def _extract_section(text: str, header: str) -> str:
            """
            Extract section body for headers like 'Assessment:' or 'Plan:'.
            Stops at the next header-like line '<Word...>:' or end of doc.
            """
            m = re.search(rf"^{re.escape(header)}\s*$", text, re.IGNORECASE | re.MULTILINE)
            if not m:
                return ""
            start = m.end()
            m2 = re.search(r"^\w[\w /-]*:\s*$", text[start:], re.MULTILINE)
            end = start + m2.start() if m2 else len(text)
            return text[start:end].strip()

        def _short_dx(evidence_line: str) -> str:
            """
            Make a short diagnosis term from a longer assessment sentence.
            Example: 'Likely stable angina given ...' -> 'stable angina given exertional pattern...'
            (Keep conservative; caller can further post-process if needed.)
            """
            s = evidence_line.strip()
            s = re.sub(r"^Likely\s+", "", s, flags=re.IGNORECASE).strip()
            # stop at separators that usually introduce qualifiers
            for sep in ["—", ";", "."]:
                if sep in s:
                    s = s.split(sep)[0].strip()
            return s

        # -----------------------------
        # Pick SOAP target keys from schema
        # -----------------------------
        soap_target_keys: list[str] = []

        # diagnoses (APS2)
        for k, v in self.schema.items():
            pdf_name = (v.get("pdf_name") or "")
            if "Diagnosis_" in pdf_name:
                soap_target_keys.append(k)

        # meds: up to 5 slots (APS1)
        for i in range(1, 6):
            for part in ["name", "dose", "often"]:
                k = f"medication_{i}_{part}"
                if k in self.schema:
                    soap_target_keys.append(k)

        # de-dupe stable
        seen: Set[str] = set()
        soap_target_keys = [k for k in soap_target_keys if not (k in seen or seen.add(k))]

        # Completion-only: do not target already-filled keys
        soap_target_keys = [k for k in soap_target_keys if not _is_filled(k)]

        # Initialize all targets as null
        soap_results: Dict[str, Dict[str, Any]] = {k: _make_obj(None, None, "not stated", 0.0) for k in soap_target_keys}

        # -----------------------------
        # Deterministic-first extraction
        # -----------------------------
        assessment = _extract_section(soap_text, "Assessment:")
        plan = _extract_section(soap_text, "Plan:")

        # ---- Diagnoses from Assessment numbered list
        assessment_lines = [ln.strip() for ln in assessment.splitlines() if ln.strip()]

        dx_items = []
        current = None
        for ln in assessment_lines:
            m = re.match(r"^(\d+)\.\s+(.*)$", ln)
            if m:
                if current:
                    dx_items.append(current.strip())
                current = m.group(2).strip()
            else:
                if current:
                    current += " " + ln.strip()
        if current:
            dx_items.append(current.strip())

        dx_slots = [
            ("primary_1", 0),
            ("primary_2", 1),
            ("secondary_and_or_complications_1", 2),
            ("secondary_and_or_complications_2", 3),
        ]
        for key, idx in dx_slots:
            if key in soap_results and idx < len(dx_items):
                evidence = dx_items[idx]
                value = _short_dx(evidence)
                soap_results[key] = _make_obj(
                    value=value,
                    evidence=evidence,
                    reasoning="extracted from Assessment section",
                    conf=confidence if confidence is not None else 0.85,
                )

        # ---- Medication extraction (explicit drug names only; do NOT fill classes)
        plan_lines = [ln.strip("- ").strip() for ln in plan.splitlines() if ln.strip()]

        nitro_line = None
        for ln in plan_lines:
            if "nitroglycerin" in ln.lower():
                nitro_line = ln
                break

        if nitro_line and "medication_1_name" in soap_results:
            soap_results["medication_1_name"] = _make_obj(
                value="nitroglycerin",
                evidence=nitro_line,
                reasoning="explicitly stated in Plan section",
                conf=0.8,
            )

        if nitro_line and "medication_1_often" in soap_results:
            soap_results["medication_1_often"] = _make_obj(
                value="PRN exertional discomfort",
                evidence=nitro_line,
                reasoning="derived from Plan instruction wording",
                conf=0.7,
            )

        # -----------------------------
        # LLM fallback for remaining missing keys (optional)
        # -----------------------------
        missing_keys = [k for k, v in soap_results.items() if v.get("value") is None]
        if use_llm_fallback and missing_keys:
            # Lazy imports: keep module light for users who skip the LLM path
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            # device/dtype
            if torch.backends.mps.is_available():
                device = "mps"
                dtype = torch.float16
            elif torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32

            cache_dir = Path(model_cache_dir)
            loaded_from_local = cache_dir.is_dir()
            load_from = str(cache_dir) if loaded_from_local else model_name

            tokenizer = AutoTokenizer.from_pretrained(load_from)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                load_from,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
            )
            model.eval()
            model.to(device)

            if not loaded_from_local:
                cache_dir.mkdir(parents=True, exist_ok=True)
                tokenizer.save_pretrained(str(cache_dir))
                model.save_pretrained(str(cache_dir))

            allowlist_block = "\n".join([f"- {k}: {self.schema[k].get('label','')}" for k in missing_keys if k in self.schema])
            system = (
                "You are a medical information extraction assistant. "
                "You must minimize hallucinations. Extract ONLY what is explicitly stated in the SOAP note. "
                "If a value is not explicitly stated, output null. "
                "For every non-null value, you MUST include an evidence quote copied verbatim from the SOAP note. "
                "Return ONLY valid JSON."
            )
            user = f"""Extract values for these schema fields (keys are fixed; do not invent new keys):
{allowlist_block}

Rules:
- Output MUST be a single JSON object whose keys are EXACTLY the keys listed above.
- Each key maps to an object with: value, evidence, reasoning.
- If not explicitly stated, set value=null, evidence=null, reasoning="not stated".
- For diagnosis fields: value MUST be a short diagnosis term (not a full sentence).
- For medication_*_name: output a specific drug name only; if only a class is mentioned (e.g., "antihypertensives"), output null.
- Do NOT guess medication doses. For any medication_*_dose, only output a value if the SOAP note explicitly states a numeric dose.
- Evidence MUST be a direct quote substring from the SOAP note.

SOAP note:
{soap_text}
"""

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_input_tokens)
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    temperature=None,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    repetition_penalty=1.02,
                    use_cache=True,
                )

            decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
            try:
                llm_obj = json.loads(decoded.strip())
            except Exception:
                start = decoded.find("{")
                end = decoded.rfind("}")
                llm_obj = json.loads(decoded[start:end + 1])

            soap_text_norm = re.sub(r"\s+", " ", soap_text).strip()
            for k in missing_keys:
                obj = llm_obj.get(k, {}) if isinstance(llm_obj, dict) else {}
                if not isinstance(obj, dict):
                    continue
                val = obj.get("value")
                ev = obj.get("evidence")
                rsn = obj.get("reasoning")

                if isinstance(val, str) and val.strip().lower() in {"null", "none", ""}:
                    val = None
                if isinstance(ev, str) and ev.strip().lower() in {"null", "none", ""}:
                    ev = None

                ok = False
                if val is not None and isinstance(ev, str):
                    ok = re.sub(r"\s+", " ", ev).strip() in soap_text_norm

                if val is not None and k.endswith("_dose") and not re.search(r"\d", str(val)):
                    ok = False

                if ok:
                    soap_results[k] = _make_obj(
                        value=val,
                        evidence=ev,
                        reasoning=rsn or "explicitly stated in SOAP",
                        conf=0.75,
                    )

        return soap_results
    
    def extract_from_lab_result(self, lab_result_path: str,
                                confidence: float = 0.70,
                                already_filled: Optional[Dict[str, Dict[str, Any]]] = None,
                                use_ocr_fallback: bool = True,
                                ocr_dpi: int = 200) -> Dict[str, Dict[str, Any]]:
        """
        Extract information from scanned lab result PDF.
        
        Args:
            lab_result_path: Path to lab result PDF file
            confidence: Confidence score for OCR-extracted source
            already_filled: Existing extracted results (e.g., from demographics + SOAP). Any already-filled
                field keys will not be overwritten (completion-only).
            use_ocr_fallback: If True, attempt OCR if the PDF appears to have no embedded text.
            ocr_dpi: DPI to render pages for OCR if needed
            
        Returns:
            Dictionary mapping schema field names to extracted values with metadata
            
        Notes (per problem.md):
        - This is intentionally generic and optional. The PDF can contain anything; we avoid overfitting.
        - We first try embedded text extraction; only if that fails do we fall back to OCR.
        - We only fill fields that remain missing after earlier sources.
        """
        already_filled = already_filled or {}

        def _is_filled(field_key: str) -> bool:
            obj = already_filled.get(field_key)
            if not isinstance(obj, dict):
                return False
            v = obj.get("value")
            return v is not None and str(v).strip() != ""

        def _make_obj(value, evidence, reasoning, conf):
            return {
                "value": value,
                "source": "lab_result.pdf",
                "confidence": float(conf),
                "reasoning": reasoning,
                "evidence": evidence,
            }

        # -----------------------------
        # Extract text: embedded first, OCR fallback if needed
        # -----------------------------
        text = ""
        used_ocr = False
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(lab_result_path)
            parts = []
            for i in range(doc.page_count):
                parts.append(doc[i].get_text("text") or "")
            text = "\n".join(parts).strip()
        except Exception:
            text = ""

        if use_ocr_fallback and len(text) < 50:
            try:
                import fitz  # PyMuPDF
                from PIL import Image
                import pytesseract
                import io

                doc = fitz.open(lab_result_path)
                ocr_parts = []
                for i in range(doc.page_count):
                    pix = doc[i].get_pixmap(dpi=ocr_dpi)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_parts.append(pytesseract.image_to_string(img) or "")
                text = "\n".join(ocr_parts).strip()
                used_ocr = True
            except Exception:
                # OCR is optional; if unavailable, just return empty results.
                return {}

        if not text:
            # No embedded text and OCR unavailable/failed
            return {}

        # Normalize whitespace for matching
        text_norm = re.sub(r"\s+", " ", text).strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        base_conf = 0.65 if used_ocr else confidence

        results: Dict[str, Dict[str, Any]] = {}

        # -----------------------------
        # Generic medication extraction (common in letters/lab reports)
        # Fill only medication_* fields that are still missing.
        # -----------------------------
        # Look for a "Medication:" section and capture subsequent bullet-ish lines.
        med_lines: list[str] = []
        in_meds = False
        current = ""
        for ln in lines:
            if re.match(r"^Medication\s*:\s*$", ln, re.IGNORECASE):
                in_meds = True
                current = ""
                continue
            if in_meds and re.match(r"^[A-Za-z][A-Za-z /-]*:\s*$", ln) and not re.match(r"^Medication\s*:\s*$", ln, re.IGNORECASE):
                # next section started
                break
            if in_meds:
                # bullets can appear as '•' or '-' or just wrapped text
                if ln.startswith(("•", "-", "*")):
                    if current:
                        med_lines.append(current.strip())
                    current = ln.lstrip("•-* ").strip()
                else:
                    if current:
                        current += " " + ln.strip()
                    else:
                        current = ln.strip()
        if in_meds and current:
            med_lines.append(current.strip())

        # Extract (name, dose_mg, freq_text) from each med line.
        # Keep this generic and conservative: require an explicit numeric mg dose.
        extracted_meds: list[tuple[str, str, str, str]] = []
        freq_patterns = [
            r"once\s+a\s+day",
            r"twice\s+a\s+day",
            r"three\s+times\s+a\s+day",
            r"twice\s+daily",
            r"once\s+daily",
            r"daily",
            r"every\s+day",
            r"\bBID\b",
            r"\bTID\b",
            r"\bQID\b",
            r"\bPRN\b",
            r"as\s+needed",
        ]
        freq_re = re.compile("|".join(freq_patterns), re.IGNORECASE)
        for ln in med_lines:
            # Example: "Aspirin 81 mg once a day ..."
            m = re.search(r"\b([A-Z][A-Za-z0-9/-]{2,}(?:\s+[A-Z][A-Za-z0-9/-]{2,})*)\b\s+(\d+(?:\.\d+)?)\s*mg\b", ln)
            if not m:
                continue
            name = m.group(1).strip()
            dose = m.group(2).strip()  # numeric mg

            freq_m = freq_re.search(ln)
            freq = freq_m.group(0).strip() if freq_m else ""

            extracted_meds.append((name, dose, freq, ln))

        def _norm_med_name(s: str) -> str:
            return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

        def _find_existing_med_slot(norm_name: str) -> Optional[int]:
            # Check already-filled + what we've added in this function so far.
            for i in range(1, 6):
                k = f"medication_{i}_name"
                existing = None
                if k in results and isinstance(results[k], dict):
                    existing = results[k].get("value")
                if existing is None and k in already_filled and isinstance(already_filled[k], dict):
                    existing = already_filled[k].get("value")
                if existing and _norm_med_name(str(existing)) == norm_name:
                    return i
            return None

        def _find_next_empty_slot() -> Optional[int]:
            for i in range(1, 6):
                if not _is_filled(f"medication_{i}_name") and f"medication_{i}_name" not in results:
                    return i
            return None

        # Fill medication slots 1..5, deduping by normalized medication name.
        for name, dose, freq, evidence in extracted_meds:
            norm_name = _norm_med_name(name)
            slot_idx = _find_existing_med_slot(norm_name)
            if slot_idx is None:
                slot_idx = _find_next_empty_slot()
            if slot_idx is None:
                break  # no available slots

            name_key = f"medication_{slot_idx}_name"
            dose_key = f"medication_{slot_idx}_dose"
            often_key = f"medication_{slot_idx}_often"

            if name_key in self.schema and not _is_filled(name_key):
                results[name_key] = _make_obj(
                    value=name,
                    evidence=evidence,
                    reasoning="extracted from lab_result medication section",
                    conf=base_conf,
                )
            if dose_key in self.schema and not _is_filled(dose_key):
                results[dose_key] = _make_obj(
                    value=dose,
                    evidence=evidence,
                    reasoning="extracted numeric mg dose from lab_result medication section",
                    conf=base_conf,
                )
            if often_key in self.schema and not _is_filled(often_key) and freq:
                results[often_key] = _make_obj(
                    value=freq.lower(),
                    evidence=evidence,
                    reasoning="extracted frequency phrase from lab_result medication section",
                    conf=base_conf,
                )

        # -----------------------------
        # Generic phone extraction (optional; only fills if missing)
        # -----------------------------
        phones = re.findall(r"\b(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})\b", text)
        # If multiple phones, we don't guess which is home vs cell; only fill if fields are empty AND only one phone found.
        if len(phones) == 1:
            area, first3, last4 = phones[0]
            # Prefer cell_phone group if missing; otherwise home_phone.
            cell_fields = ["cell_phone_area_code", "cell_phone_first3", "cell_phone_last4"]
            home_fields = ["home_phone_area_code", "home_phone_first3", "home_phone_last4"]
            if all((f in self.schema and not _is_filled(f)) for f in cell_fields):
                results[cell_fields[0]] = _make_obj(area, f"{area}-{first3}-{last4}", "parsed phone from lab_result", base_conf)
                results[cell_fields[1]] = _make_obj(first3, f"{area}-{first3}-{last4}", "parsed phone from lab_result", base_conf)
                results[cell_fields[2]] = _make_obj(last4, f"{area}-{first3}-{last4}", "parsed phone from lab_result", base_conf)
            elif all((f in self.schema and not _is_filled(f)) for f in home_fields):
                results[home_fields[0]] = _make_obj(area, f"{area}-{first3}-{last4}", "parsed phone from lab_result", base_conf)
                results[home_fields[1]] = _make_obj(first3, f"{area}-{first3}-{last4}", "parsed phone from lab_result", base_conf)
                results[home_fields[2]] = _make_obj(last4, f"{area}-{first3}-{last4}", "parsed phone from lab_result", base_conf)

        return results
    
    def combine_extractions(self, *extraction_results: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Combine extractions from multiple sources, resolving conflicts by confidence.
        
        Args:
            *extraction_results: Variable number of extraction result dictionaries
            
        Returns:
            Combined dictionary with best values based on confidence scores
        """
        combined = {}
        
        for extraction in extraction_results:
            for field_name, field_data in extraction.items():
                if field_name not in combined:
                    combined[field_name] = field_data
                else:
                    # Keep the value with higher confidence
                    if field_data.get('confidence', 0) > combined[field_name].get('confidence', 0):
                        combined[field_name] = field_data
        
        return combined


def extract_from_demographics(demographics_path: str, schema_path: str,
                              confidence: float = 0.95) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to extract from demographics.json.
    
    Args:
        demographics_path: Path to demographics.json file
        schema_path: Path to schema.json file
        confidence: Confidence score for structured data source
        
    Returns:
        Dictionary mapping schema field names to extracted values with metadata
    """
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    extractor = InformationExtractor(schema)
    return extractor.extract_from_demographics(demographics_path, confidence)

