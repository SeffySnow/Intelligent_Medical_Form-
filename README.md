# Waive Take-Home — AI-Assisted Medical Form Understanding & Population

### Why this matters
As a candidate, I treated this as an **AI-engineering reliability problem**, not a “prompting” problem.

The hard part is not producing *some* output — it’s producing output that is:
- **Correct** when sources conflict or are incomplete
- **Traceable** to a source (so a reviewer can audit it)
- **Conservative** (leave fields blank rather than hallucinating)
- **Reproducible** (runs locally, open-source only, deterministic where possible)

I solved this by building a **source-ranked extraction pipeline** with validation:
- Use **fillable PDF metadata** to derive a stable schema (`schema.json`)
- Use **deterministic parsing** for structured sources (e.g., `demographics.json`) to avoid LLM mismatch/hallucination
- Use **evidence-gated extraction** for noisy text (`soap_notes.txt`) and generic PDFs (`lab_result.pdf`)
- Produce `answers.json` with **value + source + reasoning + confidence**
- Populate the fillable PDF into `populated.pdf` (text fields only), and verify values exist in the output PDF

---

### Scope (what I chose to solve and why)
- **Supported form**: `form_fillable.pdf` (AcroForm metadata).  
  - **Also supported (not used in `main.ipynb`)**: `form_scanned.pdf` schema extraction via OCR + layout parsing (implemented as a fallback for non-fillable PDFs).
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

**Why normalize field keys (engineering reason)**
The raw PDF field names (e.g., `APS1. areacode`, `APS1.Date_last_d`) are stable for population, but they are not ideal as pipeline keys. I normalize them into descriptive, deterministic keys to prevent:
- **LLM key hallucination** (models invent “close” keys)
- **Key mismatch** across stages (extraction → reconciliation → `answers.json` → population)
- **Ambiguity** in repeated fields (medication slots, date parts)

Examples of normalized keys produced from metadata:

```text
home_phone_area_code:
  Label: Home Phone # (+ Area Code)
  PDF Name: APS1. areacode
  Type: text
  Group: home_phone, Part: area_code

address_street_city_province_postal_code:
  Label: Address (Street, City, Province, Postal Code)
  PDF Name: APS1.Address
  Type: text

contract_or_policy:
  Label: Contract or Policy #
  PDF Name: APS1.Contract
  Type: text

date_last_day:
  Label: Date Last Worked (dd)
  PDF Name: APS1.Date_last_d
  Type: text
  Group: date_last, Part: day
```

**Scanned/non-fillable fallback (not used in `main.ipynb`)**
- Implemented in `src/scanned_schema_extraction.py`
- Uses **OCR + simple layout parsing** to propose text-field bboxes and labels for `form_scanned.pdf`.
- Not wired into the notebook because the current form is fillable and metadata extraction is more reliable; the code exists as a fallback for other PDF formats where AcroForm fields are unavailable.

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

**Extra reliability work I added (beyond the bare minimum)**
Even though `problem.md` only requires a small end-to-end slice, I intentionally added a few “production-minded” details that make the system more robust without overfitting:
- **Embedded-text-first, OCR fallback second**: `extract_from_lab_result(..., use_ocr_fallback=True)` prefers embedded text when present and only uses OCR when necessary. This reduces OCR noise and runtime on PDFs that already contain text.
- **Tunable OCR quality**: the OCR path exposes `ocr_dpi` (default 200) because DPI is a practical trade-off between OCR accuracy and compute/memory. This is the kind of knob you end up needing in real pipelines.
- **Medication dedup across sources**: if a medication already exists from SOAP (e.g., nitroglycerin), lab parsing merges dose/frequency into the same slot rather than duplicating the drug in a new slot. This prevents “double counting” in the final populated form.

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

**Why Qwen for the local LLM fallback**
- **Low operational overhead**: `Qwen/Qwen2.5-3B-Instruct` is not gated, so it can be pulled without Hugging Face authentication/approval steps.
- **Good structured output adherence**: with a strict prompt + evidence-gating, it reliably produces JSON-shaped outputs for the constrained extraction task.

**Prompt design (system + user) and hallucination mitigation**
This is the part I treated as “prompt engineering” in the way `problem.md` intends: **input/output constraints + validation**, not clever prompting.

- **System prompt goals**:
  - “Extract ONLY what is explicitly stated”
  - “If not stated, output null”
  - “Return ONLY valid JSON”
  - “Every non-null value must include a verbatim evidence quote”
  These constraints push the model away from “helpful completion” and toward extractive behavior.

*Note on JSON reliability*: in a production setting, using a model/runtime that supports a **native JSON response format / constrained decoding** would be even better for this kind of task (it reduces JSON parse failures and schema drift). For this take-home, I kept the setup simple and reproducible with Qwen + strict prompting + validation.

- **User prompt structure**:
  - Provide an **allowlist** of schema keys (completion-only; no invented keys)
  - Require a fixed object shape per key (e.g., `{value, evidence, reasoning}`)
  - Add **field-specific guardrails**, e.g.:
    - diagnosis values must be short (not full sentences)
    - medication doses require an explicit numeric dose
    - medication names must be specific drugs (not classes like “antihypertensives”)

- **Symbolic post-validation (the real hallucination reducer)**:
  - Evidence gating: drop any extraction whose `evidence` is not a substring of the source text.
  - Dose validation: drop dose fields unless they contain numeric content.
  - Completion-only targeting: only query remaining missing keys after deterministic extraction.

This combination directly matches what `problem.md` calls out: **prompt design, input/output constraints, validation, and strategies to reduce hallucination**, plus a balance of deterministic + model-based reasoning.

**Why no LLM for `demographics.json`**
`demographics.json` is already structured ground truth. Using an LLM there adds:
- unnecessary latency/cost
- risk of format drift (e.g., splitting phones/dates incorrectly)
- risk of hallucinating values that don’t exist

So I keep demographics extraction fully deterministic and validated.

**Why an LLM for `soap_notes.txt` (instead of pure regex)**
SOAP notes contain variability that is hard to robustly capture with regex alone (shorthand, typos, partial phrasing). The design here is:
- Do deterministic extraction where structure exists (section headers, numbered Assessment)
- Use an LLM only as a fallback for the remainder, under strict constraints:
  - completion-only targeting
  - evidence-gated outputs
  - guardrails for common hallucinations (e.g., numeric dose required)

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
- Improve scanned-form schema extraction quality (more robust box detection + label association) and align its bboxes to a consistent coordinate system across PDF/image rendering.
- Expand checkbox/radio/choice population with safe option mapping + confidence.
- Improve diagnosis normalization (e.g., “stable angina” vs longer phrase) while keeping evidence intact.
- Add a small “golden” ground truth set and compute precision/recall on a few target fields.
- Add more robust document-type routing (e.g., determine which doc likely contains which field).


