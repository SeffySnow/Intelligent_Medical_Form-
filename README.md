# Waive Take-Home — AI-Assisted Medical Form Understanding & Population

### Why this matters
Insurance/disability workflows often rely on **semi-structured medical forms** filled from a bundle of patient documents. In practice, pipelines must be **reliable, auditable, and conservative**: they should extract what is truly supported by evidence, avoid hallucinations, and surface uncertainty.

This project implements a **pragmatic end-to-end slice**:
- Extract a form field schema from a **fillable PDF**
- Extract values from multiple patient documents (**structured + unstructured + “lab pdf can be anything”**)
- Produce a **confidence-aware mapping** with citations in `answers.json`
- **Populate** the fillable PDF (text fields only) into `populated.pdf`
- Include a small **evaluation** section focused on reliability

---

### Scope (what I chose to solve and why)
- **Supported form**: `form_fillable.pdf` (AcroForm metadata).  
  - **Not fully covered**: `form_scanned.pdf` (would require OCR + layout parsing; out of scope for a 4–6h slice).
- **Population**: **text fields only** (skip checkboxes/radios/choice fields) to keep behavior deterministic and avoid incorrect selections.
- **Information sources**:
  - `demographics.json` (anchor truth for identity/contact/DOB/address)
  - `soap_notes.txt` (noisy clinical note; used to fill diagnoses + explicit meds)
  - `lab_result.pdf` (treated as **generic**; parse embedded text first, OCR fallback is optional)
- **Reliability stance**:
  - Do **not** overwrite structured demographics with noisier sources unless explicitly desired (we prefer “fill missing”).
  - Require **evidence-backed extraction** for SOAP/LLM outputs.
  - Prefer “leave blank” over guessing (especially for medication dose).

---

### Pipeline architecture & design decisions

#### **1) Schema extraction (`schema.json`)**
- Implemented in `src/schema_extraction.py`
- Approach:
  - Use **AcroForm field metadata** via `pypdf` for field names/labels/types
  - Use **widget bounding boxes** via `PyMuPDF` for spatial metadata
  - Normalize field keys and add lightweight grouping (e.g., split date fields into `*_day/_month/_year`, phone into `area_code/first3/last4`, medication slots)

#### **2) Multi-source information extraction (`answers.json`)**
Implemented in `src/information_extraction.py`:
- **Demographics (anchor)**: deterministic mapping + parsing (phones/DOB/address)
- **SOAP (noisy)**: “deterministic-first + evidence-gated” extraction:
  - Extract diagnoses from `Assessment:` numbered items
  - Extract explicit meds from `Plan:` when a specific drug is named
  - Optional LLM fallback for remaining missing keys (open-source local model)
- **Lab result PDF (generic, optional)**:
  - Extract embedded PDF text first (fast, reliable)
  - If text is absent, optionally OCR pages (requires Tesseract binary)
  - Generic medication parsing (drug + mg dose + frequency)
  - Deduplicate medication names across sources/slots to avoid repeated entries

#### **3) Reconciliation + confidence**
- Reconciliation is “best-effort + conservative”:
  - Keep `demographics.json` values as high confidence
  - SOAP/lab only fill missing fields (completion-only) and avoid overwriting unless explicitly flagged
- Confidence heuristic is intentionally simple and explainable:
  - **Structured** sources ~0.95
  - SOAP explicit extraction ~0.7–0.8 (evidence-backed)
  - Lab extraction ~0.7 (embedded text) or ~0.65 (OCR)

#### **4) PDF population (`populated.pdf`)**
- Implemented in `src/pdf_population.py`
- Text fields only:
  - Map from `schema.json` normalized keys → `pdf_name` (AcroForm field name)
  - Write values from `answers.json` into `form_fillable.pdf`
  - Preserve AcroForm fields by cloning writer from the source PDF (avoid losing form fields)

---

### Where / why / how AI was used (and prompt strategies)
AI is used **judiciously** only where it helps with noisy text:
- **SOAP extraction** uses a “deterministic-first” pass (highest precision).  
  If enabled, an **open-source local LLM** (default `Qwen/Qwen2.5-3B-Instruct`) is used as a fallback for still-missing SOAP-relevant keys.

Key strategies to reduce hallucination:
- **Completion-only targeting**: only ask for fields not already filled by structured sources.
- **Evidence gating**: every non-null extraction must include a verbatim quote from the source.
- **Guardrails**: medication dose fields require explicit numeric dose; otherwise remain null.
- **Model caching**: model/tokenizer are cached under `./models/` to avoid re-downloads.

---

### Mini evaluation summary (what we test)
Included in Task 5 of `main.ipynb`:
- **Formatting consistency**: DOB/phone parts are the expected digit lengths
- **SOAP hallucination checks**:
  - evidence substring match rate
  - “no invented dose” trap
- **Medication sanity**:
  - numeric dose check
  - frequency whitelist check
  - dedupe check across medication slots
- **PDF population verification**: read back AcroForm `/V` values from `populated.pdf`

---

### How to run

#### **Install**
Create and activate a virtual environment, then:

```bash
pip install -r requirements.txt
```

#### **Run**
Open and run `main.ipynb` top-to-bottom. It will produce:
- `schema.json`
- `answers.json`
- `populated.pdf`

---

### Key challenges / trade-offs
- **Noisy vs structured conflicts**: SOAP notes can omit or shorten names (e.g., “Peter Fern” vs “Peter Julius Fern”). We treat `demographics.json` as the anchor for identity/contact.
- **Generic lab PDF**: the take-home warns not to overfit `lab_result.pdf`. We use generic text extraction and conservative parsing; OCR is optional fallback only.
- **PDF population pitfalls**: writing pages without cloning AcroForm can drop fields entirely. We preserve the form structure by cloning from the reader.

---

### Next steps (if more time/resources)
- Support `form_scanned.pdf` with OCR + layout parsing (e.g., LayoutParser) and alignment to schema fields.
- Expand checkbox/radio/choice population with safe option mapping + confidence.
- Improve diagnosis normalization (e.g., “stable angina” vs longer phrase) while keeping evidence intact.
- Add a small “golden” ground truth set and compute precision/recall on a few target fields.
- Add more robust document-type routing (e.g., determine which doc likely contains which field).


