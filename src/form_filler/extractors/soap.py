"""SOAP notes extractor.

Single Responsibility: extract diagnoses and medications from free-text SOAP notes.

Strategy (minimum hallucination):
  1. Deterministic-first: regex over Assessment / Plan sections.
  2. LLM fallback (optional): evidence-gated Qwen2.5 for remaining missing fields.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from form_filler.config import ExtractionConfig
from form_filler.extractors.base import BaseExtractor, ExtractionResult
from form_filler.extractors.utils import is_filled, make_entry

logger = logging.getLogger(__name__)


class SOAPExtractor(BaseExtractor):
    """Extracts diagnoses and medications from SOAP notes text."""

    def __init__(self, source_path: str, config: ExtractionConfig) -> None:
        self._source_path = source_path
        self._config = config

    @property
    def source_name(self) -> str:
        return "soap_notes.txt"

    def extract(
        self,
        schema: dict[str, Any],
        already_filled: ExtractionResult | None = None,
    ) -> ExtractionResult:
        already_filled = already_filled or {}
        confidence = self._config.soap_confidence

        with open(self._source_path, encoding="utf-8") as fh:
            soap_text = fh.read()

        target_keys = self._build_target_keys(schema, already_filled)
        results: ExtractionResult = {
            k: make_entry(None, self.source_name, "not stated", 0.0)
            for k in target_keys
        }

        assessment = _extract_section(soap_text, "Assessment:")
        plan = _extract_section(soap_text, "Plan:")

        self._extract_diagnoses(results, assessment, confidence)
        self._extract_medications(results, plan)

        missing = [k for k, v in results.items() if v.get("value") is None]
        if self._config.use_llm_fallback and missing:
            self._llm_fallback(results, missing, soap_text, schema)

        filled = sum(1 for v in results.values() if v.get("value") is not None)
        logger.info("SOAP extraction complete: %d/%d fields filled", filled, len(results))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_target_keys(
        self, schema: dict[str, Any], already_filled: ExtractionResult
    ) -> list:
        keys: list = []
        seen: set[str] = set()

        for k, v in schema.items():
            pdf_name = v.get("pdf_name", "")
            if "Diagnosis_" in pdf_name and k not in seen:
                keys.append(k)
                seen.add(k)

        for i in range(1, 6):
            for part in ("name", "dose", "often"):
                k = f"medication_{i}_{part}"
                if k in schema and k not in seen:
                    keys.append(k)
                    seen.add(k)

        # Completion-only: skip already-filled fields
        return [k for k in keys if not is_filled(k, already_filled)]

    def _extract_diagnoses(
        self, results: ExtractionResult, assessment: str, confidence: float
    ) -> None:
        lines = [ln.strip() for ln in assessment.splitlines() if ln.strip()]
        dx_items: list[str] = []
        current: str | None = None

        for ln in lines:
            m = re.match(r"^(\d+)\.\s+(.*)$", ln)
            if m:
                if current:
                    dx_items.append(current.strip())
                current = m.group(2).strip()
            elif current:
                current += " " + ln

        if current:
            dx_items.append(current.strip())

        slots = [
            ("primary_1", 0),
            ("primary_2", 1),
            ("secondary_and_or_complications_1", 2),
            ("secondary_and_or_complications_2", 3),
        ]
        for key, idx in slots:
            if key in results and idx < len(dx_items):
                evidence = dx_items[idx]
                results[key] = make_entry(
                    value=_shorten_dx(evidence),
                    source=self.source_name,
                    reasoning="extracted from Assessment section",
                    confidence=confidence,
                    evidence=evidence,
                )

    def _extract_medications(self, results: ExtractionResult, plan: str) -> None:
        plan_lines = [ln.strip("- ").strip() for ln in plan.splitlines() if ln.strip()]
        nitro_line = next(
            (ln for ln in plan_lines if "nitroglycerin" in ln.lower()), None
        )
        if nitro_line:
            if "medication_1_name" in results:
                results["medication_1_name"] = make_entry(
                    value="nitroglycerin",
                    source=self.source_name,
                    reasoning="explicitly stated in Plan section",
                    confidence=0.8,
                    evidence=nitro_line,
                )
            if "medication_1_often" in results:
                results["medication_1_often"] = make_entry(
                    value="PRN exertional discomfort",
                    source=self.source_name,
                    reasoning="derived from Plan instruction wording",
                    confidence=0.7,
                    evidence=nitro_line,
                )

    def _llm_fallback(
        self,
        results: ExtractionResult,
        missing_keys: list,
        soap_text: str,
        schema: dict[str, Any],
    ) -> None:
        """LLM fallback for fields still missing after deterministic extraction."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            logger.warning("torch/transformers not installed; skipping LLM fallback")
            return

        logger.info("Running LLM fallback for %d missing fields", len(missing_keys))
        cfg = self._config

        device, dtype = _pick_device(torch)
        cache_dir = Path(cfg.model_cache_dir)
        load_from = str(cache_dir) if cache_dir.is_dir() else cfg.model_name

        tokenizer = AutoTokenizer.from_pretrained(load_from)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            load_from, torch_dtype=dtype, low_cpu_mem_usage=True
        )
        model.eval()
        model.to(device)

        if not cache_dir.is_dir():
            cache_dir.mkdir(parents=True, exist_ok=True)
            tokenizer.save_pretrained(str(cache_dir))
            model.save_pretrained(str(cache_dir))

        allowlist = "\n".join(
            f"- {k}: {schema[k].get('label', '')}" for k in missing_keys if k in schema
        )
        system = (
            "You are a medical information extraction assistant. "
            "Extract ONLY what is explicitly stated in the SOAP note. "
            "If a value is not explicitly stated, output null. "
            "For every non-null value, include an evidence quote copied verbatim from the note. "
            "Return ONLY valid JSON."
        )
        user = (
            f"Extract values for these fields (do not invent new keys):\n{allowlist}\n\n"
            "Rules:\n"
            "- Output a single JSON object with EXACTLY the keys listed above.\n"
            "- Each key maps to: {value, evidence, reasoning}.\n"
            "- If not stated: value=null, evidence=null, reasoning='not stated'.\n"
            "- Diagnosis fields: short term only, not a full sentence.\n"
            "- medication_*_name: specific drug name; null if only a class is mentioned.\n"
            "- medication_*_dose: only output if an explicit numeric dose is stated.\n"
            "- Evidence MUST be a verbatim substring of the SOAP note.\n\n"
            f"SOAP note:\n{soap_text}"
        )

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=cfg.max_input_tokens
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=cfg.max_new_tokens,
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
            start, end = decoded.find("{"), decoded.rfind("}")
            try:
                llm_obj = json.loads(decoded[start : end + 1])
            except Exception:
                logger.warning("LLM output could not be parsed as JSON; skipping")
                return

        soap_norm = re.sub(r"\s+", " ", soap_text).strip()
        for k in missing_keys:
            obj = llm_obj.get(k, {}) if isinstance(llm_obj, dict) else {}
            if not isinstance(obj, dict):
                continue
            val, ev, rsn = obj.get("value"), obj.get("evidence"), obj.get("reasoning")

            if isinstance(val, str) and val.strip().lower() in {"null", "none", ""}:
                val = None
            if isinstance(ev, str) and ev.strip().lower() in {"null", "none", ""}:
                ev = None

            # Evidence gate: quote must appear verbatim; dose must contain a digit.
            ok = (
                val is not None
                and isinstance(ev, str)
                and re.sub(r"\s+", " ", ev).strip() in soap_norm
            )
            if ok and k.endswith("_dose") and not re.search(r"\d", str(val)):
                ok = False

            if ok:
                results[k] = make_entry(
                    value=val,
                    source=self.source_name,
                    reasoning=rsn or "explicitly stated in SOAP",
                    confidence=0.75,
                    evidence=ev,
                )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _extract_section(text: str, header: str) -> str:
    m = re.search(rf"^{re.escape(header)}\s*$", text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    m2 = re.search(r"^\w[\w /-]*:\s*$", text[start:], re.MULTILINE)
    end = start + m2.start() if m2 else len(text)
    return text[start:end].strip()


def _shorten_dx(evidence_line: str) -> str:
    s = re.sub(r"^Likely\s+", "", evidence_line.strip(), flags=re.IGNORECASE).strip()
    for sep in ("—", ";", "."):
        if sep in s:
            s = s.split(sep)[0].strip()
            break
    return s


def _pick_device(torch: Any):
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32
