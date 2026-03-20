# Form-Filler — Automated Medical Form Population Pipeline

An AI-assisted pipeline that reads patient documents (structured JSON, clinical notes, lab PDFs),
extracts the relevant information, reconciles conflicts by confidence, and populates a fillable PDF form.

---

## Table of Contents

1. [What this project does](#1-what-this-project-does)
2. [Project structure — every file explained](#2-project-structure--every-file-explained)
3. [Pipeline flow — step by step](#3-pipeline-flow--step-by-step)
4. [Design principles (SOLID)](#4-design-principles-solid)
5. [How to run locally](#5-how-to-run-locally)
6. [How to deploy with Docker](#6-how-to-deploy-with-docker)
7. [How Git works with this project](#7-how-git-works-with-this-project)
8. [CI/CD pipeline explained](#8-cicd-pipeline-explained)
9. [Interview talking points](#9-interview-talking-points)

---

## 1. What this project does

Medical staff must fill out long insurance/APS forms from scattered patient documents. This project automates that:

```
inputs/
  demographics.json   →  structured patient data (name, DOB, phones, address)
  soap_notes.txt      →  unstructured clinical note (diagnoses, medications)
  lab_result.pdf      →  lab report PDF (medications, contact info)
  form_fillable.pdf   →  the blank AcroForm PDF to be filled

            ↓  pipeline  ↓

outputs/
  schema.json         →  discovered form field structure
  answers.json        →  extracted answers with source + confidence
  populated.pdf       →  the completed form
```

**Core design stance:** treat this as a *reliability* problem, not a prompting problem.
Every answer is traceable to a source, conservative (blank beats hallucination), and reproducible.

---

## 2. Project structure — every file explained

```
Form-Filler/
│
├── .claude/                      ← Claude AI assistant config (local only)
├── .github/workflows/ci.yml      ← GitHub Actions CI pipeline
├── .dockerignore                 ← files excluded from Docker image
├── .env.example                  ← template for environment variables
├── .gitignore                    ← files Git never tracks
├── Dockerfile                    ← container definition
├── pyproject.toml                ← Python package definition + tool config
├── requirements.txt              ← legacy dep list (pre-refactor, kept for reference)
├── README.md                     ← this file
├── problem.md                    ← original take-home challenge brief
│
├── inputs/                       ← ALL read-only source documents
│   ├── form_fillable.pdf         ← the AcroForm PDF to populate
│   ├── form_scanned.pdf          ← scanned (non-fillable) version (optional fallback)
│   ├── demographics.json         ← structured patient record
│   ├── soap_notes.txt            ← clinical SOAP note (free text)
│   └── lab_result.pdf            ← lab report PDF
│
├── outputs/                      ← ALL generated files (gitignored)
│   ├── .gitkeep                  ← keeps this empty folder tracked by Git
│   ├── schema.json               ← extracted form field schema (Step 1 output)
│   ├── answers.json              ← reconciled answers (Step 2 output)
│   └── populated.pdf             ← filled form (Step 3 output)
│
├── models/                       ← local LLM cache (gitignored, large)
│   └── Qwen2.5-3B-Instruct/      ← Qwen model weights + tokenizer
│
├── src/
│   └── form_filler/              ← installable Python package
│       ├── __init__.py           ← package marker + version
│       ├── config.py             ← all configuration (paths, settings)
│       ├── logging_config.py     ← logging setup (console vs JSON)
│       ├── pipeline.py           ← orchestrator: runs all steps in order
│       ├── reconciler.py         ← merges extraction results by confidence
│       ├── pdf_populator.py      ← writes values into the AcroForm PDF
│       ├── cli.py                ← command-line entry point
│       │
│       ├── schema/
│       │   ├── __init__.py
│       │   └── acroform.py       ← extracts field schema from fillable PDFs
│       │
│       └── extractors/
│           ├── __init__.py
│           ├── base.py           ← abstract BaseExtractor (the interface)
│           ├── utils.py          ← pure helper functions (parse_date, etc.)
│           ├── demographics.py   ← extracts from demographics.json
│           ├── soap.py           ← extracts from SOAP notes (+ LLM fallback)
│           └── lab.py            ← extracts from lab result PDF (+ OCR fallback)
│
├── tests/
│   ├── conftest.py               ← shared fixtures (test data, temp files)
│   ├── test_config.py
│   ├── test_utils.py
│   ├── test_demographics_extractor.py
│   ├── test_soap_extractor.py
│   ├── test_lab_extractor.py
│   ├── test_reconciler.py
│   ├── test_pdf_populator.py
│   └── test_pipeline.py
│
└── main.ipynb                    ← original exploratory notebook (still runnable)
```

---

### File-by-file explanation

#### `.claude/settings.local.json`

This is a configuration file for **Claude Code** (the AI coding assistant used to build this project).
It stores a list of pre-approved shell commands that Claude is allowed to run without asking for confirmation each time — things like running the test suite (`pytest`) or the linter (`ruff`).

**It has zero effect on how the project runs.** It is local-only (never committed to GitHub) and only matters when you are actively using Claude Code as a development tool. Think of it as the assistant's "allowed actions" list.

---

#### `.github/workflows/ci.yml`

This is the **Continuous Integration (CI) pipeline** that runs automatically on GitHub every time you push code or open a pull request.

It has three jobs that run in order:

```
push to GitHub
      ↓
 1. lint     → ruff checks code style (fails fast if there are obvious issues)
      ↓
 2. test     → pytest runs all 80 unit tests + uploads coverage report
      ↓
 3. docker   → builds the Docker image to confirm it compiles cleanly
```

If any step fails, GitHub shows a red ✗ and blocks the PR from being merged. This catches bugs before they reach production.

---

#### `.dockerignore`

Tells Docker which files to **exclude** when building the image. Excluded: `.git/`, `venv/`, notebooks, `models/` (large — mounted at runtime), test files, markdown docs.

Why it matters: without this, `docker build` would copy gigabytes of model weights and git history into the image, making it huge and slow to push/pull.

---

#### `.env.example`

A **template** showing every environment variable the app understands. You copy this to `.env` for local development:

```bash
cp .env.example .env
# edit .env with your actual paths / settings
```

In production (Docker, cloud), you pass these as real environment variables instead of a file. The `.env` file itself is gitignored — `.env.example` (safe to commit) documents what's needed.

---

#### `.gitignore`

Tells Git which files to **never track**. Key entries:

| Pattern | Why ignored |
|---|---|
| `__pycache__/`, `*.pyc` | Compiled Python bytecode — regenerated automatically |
| `venv/`, `.venv/` | Virtual environment — recreated from `pyproject.toml` |
| `models/` | LLM model weights (gigabytes) — not for version control |
| `outputs/*` | Generated files — reproducible from inputs |
| `!outputs/.gitkeep` | Exception: keep the empty `outputs/` folder itself |
| `.env` | Contains local secrets/paths — never commit |
| `.ipynb_checkpoints/` | Jupyter auto-saves — noise |

---

#### `Dockerfile`

Defines how to build a **reproducible, isolated container** for the app. It uses a two-stage build:

**Stage 1 — builder:**
```dockerfile
FROM python:3.11-slim AS builder
# Installs all dependencies into /deps (isolated from the final image)
```

**Stage 2 — runtime:**
```dockerfile
FROM python:3.11-slim AS runtime
# Copies only the installed packages + source code (no build tools)
# Runs as a non-root user (security best practice)
# Expects /data/inputs/ and /data/outputs/ to be mounted as volumes
```

Why two stages? The builder stage needs `gcc`, `setuptools`, `wheel`, etc. to compile packages.
The runtime stage doesn't — stripping them keeps the final image small and the attack surface minimal.

---

#### `pyproject.toml`

The **single source of truth** for the Python package. Replaces the old `requirements.txt` approach.

Key sections:

```toml
[project]
name = "form-filler"
version = "0.1.0"
dependencies = [...]          # runtime deps (always installed)

[project.optional-dependencies]
ocr = [pytesseract, Pillow, opencv-python]   # only if you need OCR
dev = [pytest, ruff, mypy]                   # only for development

[project.scripts]
form-filler = "form_filler.cli:main"         # registers the CLI command

[tool.pytest.ini_options]                    # pytest config
[tool.ruff]                                  # linter config
[tool.mypy]                                  # type checker config
```

After `pip install -e .`, you can run `form-filler` as a command from anywhere.

---

#### `src/form_filler/__init__.py`

Marks `form_filler` as a Python package and exposes the version number.

```python
__version__ = "0.1.0"
```

Used by: `pip show form-filler`, `import form_filler; form_filler.__version__`

---

#### `src/form_filler/config.py`

**All configuration lives here.** Two dataclasses:

- `ExtractionConfig` — controls AI/OCR behaviour (confidence thresholds, LLM model name, OCR DPI, token limits)
- `PipelineConfig` — controls file paths and logging

The `PipelineConfig.from_env()` class method reads every setting from environment variables, falling back to sensible defaults. This is how the same code runs locally (reads `.env`) and in Docker (reads container env vars) without any code changes.

```python
# Local dev: reads from .env file (via python-dotenv)
config = PipelineConfig.from_env()

# Docker: reads from -e flags or docker-compose environment section
# Same code path, different source of env vars
```

---

#### `src/form_filler/logging_config.py`

Sets up structured logging with two modes controlled by `LOG_FORMAT`:

- `console` (default for dev) — human-readable: `2024-01-15T10:30:00 [INFO] pipeline: Step 1/3...`
- `json` (default in Docker) — machine-readable: `{"level":"INFO","message":"Step 1/3...","module":"pipeline"}`

JSON logs are what cloud log aggregators (Datadog, CloudWatch, Grafana Loki) expect so they can be searched and filtered.

---

#### `src/form_filler/schema/acroform.py` — `SchemaExtractor`

**Step 1 of the pipeline.** Reads the fillable PDF and discovers all its form fields.

Uses two libraries together:
- `pypdf` — reads AcroForm metadata (field name, type, tooltip/label)
- `PyMuPDF` — reads widget bounding boxes and page numbers

Why two libraries? `pypdf` gives you the *what* (labels and types) but not the *where*. `PyMuPDF` gives you the *where* (pixel coordinates). Together they produce a complete field description.

It normalises raw PDF field names into clean, consistent keys:
```
"APS1. areacode"  →  "home_phone_area_code"
"APS1.Date_of_birth_d"  →  "date_of_birth_dd"
"APS1.Medication1"  →  "medication_1_name"
```
This normalisation prevents LLM hallucination of field names later in the pipeline.

---

#### `src/form_filler/extractors/base.py` — `BaseExtractor`

The **abstract interface** that all extractors must implement. This is the Dependency Inversion Principle in action — the `Pipeline` class never knows which concrete extractor it's talking to; it only knows this interface:

```python
class BaseExtractor(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...      # "demographics.json", "soap_notes.txt", etc.

    @abstractmethod
    def extract(self, schema, already_filled) -> dict: ...
```

`already_filled` is the key parameter: it contains everything extracted so far, allowing each extractor to skip fields that are already known (**completion-only targeting**).

---

#### `src/form_filler/extractors/utils.py`

**Pure helper functions** — no file I/O, no side effects. Because they're pure, they're the easiest things to test.

| Function | Purpose |
|---|---|
| `parse_date("1960-04-15")` | → `{"day": "15", "month": "04", "year": "1960"}` |
| `parse_phone("6136565890")` | → `{"area_code": "613", "first3": "656", "last4": "5890"}` |
| `format_address({"street": ...})` | → `"45 Maple Ave, Toronto, ON, K7L 3V8"` |
| `is_filled("field_key", already_filled)` | → `True` if value is non-empty |
| `make_entry(value, source, reasoning, confidence)` | → standardised answer dict |

---

#### `src/form_filler/extractors/demographics.py` — `DemographicsExtractor`

**Highest confidence extractor (0.95).** Reads `demographics.json` and maps every field deterministically — no AI involved. Uses `utils.py` for all transformations.

What it extracts:
- Patient name (direct copy)
- Date of birth → split into DD / MM / YYYY
- Home phone → split into area code / first-3 / last-4
- Cell phone → same split
- Address → formatted single string

Because this data is structured and machine-generated, it's treated as ground truth. Later extractors won't overwrite these fields unless they have higher confidence (they won't).

---

#### `src/form_filler/extractors/soap.py` — `SOAPExtractor`

**Medium confidence extractor (0.75).** Processes free-text clinical notes in two passes:

**Pass 1 — Deterministic (always runs):**
- Finds the `Assessment:` section, extracts numbered diagnosis items with regex
- Finds `nitroglycerin` in the `Plan:` section (explicitly mentioned drug)
- Result: fills `primary_1`, `primary_2`, `secondary_*`, `medication_1_name`, `medication_1_often`

**Pass 2 — LLM fallback (optional, skipped in tests):**
- Only runs for fields *still missing* after Pass 1 (completion-only)
- Loads `Qwen2.5-3B-Instruct` locally (no API calls)
- Sends a strict prompt with an allowlist of missing field keys
- **Evidence gating**: any extracted value whose evidence quote isn't found verbatim in the note is discarded
- **Dose validation**: medication dose fields are dropped unless they contain a numeric value

This two-pass design means: if the regex can find it, it does. The LLM is a fallback, not the primary tool.

---

#### `src/form_filler/extractors/lab.py` — `LabExtractor`

**Lower confidence extractor (0.70 embedded text / 0.65 OCR).** Generically processes the lab PDF — no assumptions about its structure.

**Text extraction:**
1. Try embedded text via `PyMuPDF` (fast, accurate)
2. If fewer than 50 characters extracted → OCR fallback via `pytesseract` (optional, requires Tesseract binary)

**What it looks for:**
- A `Medication:` section with bullet-point drug entries: `"Aspirin 81 mg once a day"`
- Extracts: drug name, numeric mg dose, frequency phrase
- Fills medication slots 2–5 (slot 1 is usually taken by SOAP's nitroglycerin)
- Deduplicates: if the same drug was already found by SOAP, merges dose/freq into the existing slot

---

#### `src/form_filler/reconciler.py` — `Reconciler`

**Merges multiple extraction results into one.** The rule is simple: for any field where two extractors disagree, keep whichever has higher `confidence`.

```
demographics.json  → patient_name: "Peter Julius Fern"  (confidence: 0.95)
soap_notes.txt     → patient_name: "Peter Fern"          (confidence: 0.75)

Reconciler picks:  → "Peter Julius Fern"  ✓
```

This is only a conflict resolver. In practice, because `SOAPExtractor` and `LabExtractor` use `already_filled` to skip known fields, most conflicts never arise.

---

#### `src/form_filler/pdf_populator.py` — `PDFPopulator`

**Writes the final answers into the AcroForm PDF.** Receives data as Python dicts (not file paths) — this makes it fully testable without touching the filesystem.

Key decisions:
- **Text fields only** — skips buttons, checkboxes, and dropdowns (deterministic behaviour; avoids wrong selections)
- **Clone from reader** — `PdfWriter(clone_from=reader)` preserves the AcroForm structure. A naive `PdfWriter()` drops all form fields.
- **`set_need_appearances_writer()`** — tells PDF viewers to render the filled values (some viewers skip this otherwise)
- Returns a `PopulationReport` dataclass with `filled`, `skipped`, and `missing_pdf_fields` dicts

---

#### `src/form_filler/pipeline.py` — `Pipeline`

**The orchestrator.** Depends on abstractions only — it never imports a concrete extractor directly. The concrete classes are wired in `cli.py`.

Execution order:
```
1. SchemaExtractor.extract_schema(form_pdf)         → schema dict
2. outputs/ directory created if it doesn't exist
3. For each extractor in order:
     result = extractor.extract(schema, already_filled=accumulated)
     accumulated = reconciler.merge(accumulated, result)
4. Save schema.json and answers.json
5. PDFPopulator.populate(form_pdf, schema, answers)  → populated.pdf
6. Return PipelineResult(schema, answers, output_pdf, report)
```

Each extractor receives the accumulated results of all previous extractors as `already_filled`. This is how completion-only targeting flows through the pipeline — no extractor needs to know about the others.

---

#### `src/form_filler/cli.py`

**Two responsibilities in one file:**

1. **Argument parsing** — `argparse` CLI with flags like `--form`, `--no-llm`, `--log-format`
2. **Composition root** — the ONLY place in the entire codebase where concrete classes are instantiated and wired together:

```python
pipeline = Pipeline(
    config=config,
    schema_extractor=SchemaExtractor(),
    extractors=[
        DemographicsExtractor(...),   # concrete
        SOAPExtractor(...),           # concrete
        LabExtractor(...),            # concrete
    ],
    reconciler=Reconciler(),          # concrete
    populator=PDFPopulator(),         # concrete
)
```

Everything else in the codebase receives abstractions. This one file knows the full concrete wiring. This is the **Composition Root** pattern — it makes the system easy to test (inject mocks instead of real classes) and easy to extend (add a new extractor without touching `Pipeline`).

---

#### `tests/conftest.py`

Shared **pytest fixtures** available to every test file automatically. Defines:

- `extraction_config` — a config with LLM and OCR disabled (so tests never load real models)
- `sample_schema` — a minimal schema dict covering all field groups
- `demographics_data` / `demographics_file` — sample patient data + a temp JSON file
- `soap_file` — a temp `.txt` file with realistic SOAP note content
- `lab_pdf_text` — the raw text of a mock lab report

Fixtures prevent code duplication across test files and make tests independent of the real input files in `inputs/`.

---

#### `tests/test_*.py`

Each test file covers exactly one module (Single Responsibility applies to tests too):

| File | Tests |
|---|---|
| `test_config.py` | Defaults, env var overrides, type coercion |
| `test_utils.py` | `parse_date`, `parse_phone` (4 phone formats), `format_address`, `is_filled` |
| `test_demographics_extractor.py` | Name/DOB/phone/address extraction, source tagging, empty schema |
| `test_soap_extractor.py` | Diagnosis extraction, nitroglycerin detection, completion-only skipping |
| `test_lab_extractor.py` | Medication line parsing, slot dedup — `fitz.open` mocked |
| `test_reconciler.py` | Confidence arbitration (higher wins), three-way merge, immutability |
| `test_pdf_populator.py` | Fill, skip non-text, skip empty/null — `pypdf` mocked |
| `test_pipeline.py` | Full orchestration — all dependencies mocked |

External libraries (`fitz`, `pypdf`, `torch`) are **mocked** in tests. This means tests run in milliseconds without needing a real PDF or GPU.

---

#### `inputs/` directory

All source documents the pipeline reads. These are **never modified** by the pipeline.

| File | What it is | Confidence |
|---|---|---|
| `form_fillable.pdf` | The target AcroForm PDF | N/A (structure, not data) |
| `form_scanned.pdf` | Scanned version — used by optional OCR schema extractor | N/A |
| `demographics.json` | Structured patient record (name, DOB, phones, address) | 0.95 |
| `soap_notes.txt` | Free-text clinical SOAP note | 0.75 |
| `lab_result.pdf` | Lab report PDF | 0.70 |

---

#### `outputs/` directory

Everything the pipeline **generates**. Gitignored (reproducible on demand). `.gitkeep` is a zero-byte file that keeps the empty folder tracked by Git so new clones have the directory ready.

| File | What it is |
|---|---|
| `schema.json` | 42 normalised form fields extracted from `form_fillable.pdf` |
| `answers.json` | ~21 answers with `value`, `source`, `reasoning`, `confidence` per field |
| `populated.pdf` | Filled copy of `form_fillable.pdf` |

---

#### `models/Qwen2.5-3B-Instruct/`

Local cache of the Qwen2.5 language model (3 billion parameters, ~6GB). Downloaded once on first run, reused on subsequent runs. Gitignored. Mounted as a Docker volume so it survives container restarts.

---

## 3. Pipeline flow — step by step

```
┌─────────────────────────────────────────────────────────┐
│  cli.py  (composition root)                             │
│    loads .env → builds PipelineConfig                   │
│    wires concrete classes → creates Pipeline            │
│    calls pipeline.run()                                 │
└───────────────────┬─────────────────────────────────────┘
                    │
          ┌─────────▼──────────┐
          │  SchemaExtractor   │  reads inputs/form_fillable.pdf
          │  (acroform.py)     │  → outputs/schema.json (42 fields)
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────┐
          │ DemographicsExtractor│ reads inputs/demographics.json
          │                    │  accumulated = {name, DOB, phones, address}
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────┐
          │  SOAPExtractor     │  reads inputs/soap_notes.txt
          │                    │  already_filled = demographics results
          │                    │  fills: diagnoses, nitroglycerin
          │                    │  (LLM fallback for remaining missing)
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────┐
          │   LabExtractor     │  reads inputs/lab_result.pdf
          │                    │  already_filled = demo + SOAP results
          │                    │  fills: Aspirin 81mg, Metformin 500mg
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────┐
          │    Reconciler      │  merges all results
          │                    │  higher confidence wins on conflict
          │                    │  → outputs/answers.json (~21 fields)
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────┐
          │   PDFPopulator     │  reads inputs/form_fillable.pdf
          │                    │  writes text fields from answers.json
          │                    │  → outputs/populated.pdf
          └────────────────────┘
```

---

## 4. Design principles (SOLID)

This codebase was structured around SOLID principles. Here's exactly how each applies:

**S — Single Responsibility**
Each class does exactly one thing:
- `SchemaExtractor` → discover form fields only
- `DemographicsExtractor` → extract from demographics.json only
- `SOAPExtractor` → extract from SOAP notes only
- `LabExtractor` → extract from lab PDF only
- `Reconciler` → merge results only
- `PDFPopulator` → write PDF only
- `Pipeline` → coordinate the steps only (never extracts anything itself)

**O — Open/Closed**
To add a new data source (e.g., FHIR API, EHR system), you:
1. Create `src/form_filler/extractors/fhir.py` with a class that extends `BaseExtractor`
2. Add it to the list in `cli.py`
3. Touch zero existing files

**L — Liskov Substitution**
`DemographicsExtractor`, `SOAPExtractor`, and `LabExtractor` are fully interchangeable via `BaseExtractor`. The `Pipeline` iterates `List[BaseExtractor]` and calls `.extract()` on each — it doesn't care which concrete type it is.

**I — Interface Segregation**
`BaseExtractor` exposes one method: `extract()`. There is no fat interface. Extractors only implement what they need.

**D — Dependency Inversion**
`Pipeline.__init__` receives `List[BaseExtractor]`, `Reconciler`, `PDFPopulator`, and `SchemaExtractor` — all passed in, never imported directly. `cli.py` is the only place that imports and instantiates concrete classes. This means in tests, you pass mocks.

---

## 5. How to run locally

### Prerequisites

- Python 3.10+
- (Optional) Tesseract binary for OCR: `brew install tesseract`

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd Form-Filler

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install the package (with dev dependencies)
pip install -e ".[dev]"

# Copy the env template
cp .env.example .env
# Edit .env if your file paths differ from defaults
```

### Run the pipeline

```bash
# Run with defaults (reads inputs/, writes outputs/)
form-filler

# Override a specific file
form-filler --form inputs/my_other_form.pdf --output outputs/my_result.pdf

# Disable LLM (faster, deterministic only)
form-filler --no-llm

# Use structured JSON logs
form-filler --log-format json

# See all options
form-filler --help
```

### Run tests

```bash
# All tests with coverage report
pytest

# Fast mode (stop at first failure)
pytest -x

# A specific test file
pytest tests/test_reconciler.py -v
```

### Run the linter

```bash
ruff check src/form_filler/
ruff check --fix src/form_filler/   # auto-fix safe issues
```

---

## 6. How to deploy with Docker

### Build the image

```bash
docker build -t form-filler:latest .
```

### Run with local files

```bash
# Mount your inputs and outputs directories into the container
docker run \
  -v $(pwd)/inputs:/data/inputs:ro \
  -v $(pwd)/outputs:/data/outputs \
  -v $(pwd)/models:/models \
  form-filler:latest
```

Flags explained:
- `-v $(pwd)/inputs:/data/inputs:ro` — mounts your `inputs/` folder as read-only inside the container at `/data/inputs`
- `-v $(pwd)/outputs:/data/outputs` — mounts `outputs/` as read-write so generated files land on your host machine
- `-v $(pwd)/models:/models` — mounts the LLM cache so it persists between runs (avoids re-downloading)
- `:ro` — read-only mount (security: the container cannot modify your inputs)

### Run with custom settings

```bash
docker run \
  -v $(pwd)/inputs:/data/inputs:ro \
  -v $(pwd)/outputs:/data/outputs \
  -v $(pwd)/models:/models \
  -e LOG_FORMAT=json \
  -e USE_LLM_FALLBACK=false \
  -e LOG_LEVEL=DEBUG \
  form-filler:latest
```

### Use docker-compose (recommended for repeated use)

```yaml
# docker-compose.yml
services:
  form-filler:
    image: form-filler:latest
    volumes:
      - ./inputs:/data/inputs:ro
      - ./outputs:/data/outputs
      - ./models:/models
    environment:
      LOG_FORMAT: json
      USE_LLM_FALLBACK: "true"
```

```bash
docker-compose up
```

### Why Docker for this project?

This pipeline has many native dependencies (PyMuPDF C bindings, PyTorch, optionally Tesseract). Docker packages all of them together so the pipeline runs identically on any machine — no "it works on my machine" issues. The model weights are kept outside the image (mounted as a volume) so the image itself stays manageable (~1–2GB).

---

## 7. How Git works with this project

### What Git tracks vs. ignores

```
Tracked (committed):                  Ignored:
  src/form_filler/**/*.py               venv/
  tests/**/*.py                         models/          (gigabytes)
  pyproject.toml                        outputs/*        (generated)
  Dockerfile                            .env             (secrets/local)
  .github/workflows/ci.yml             __pycache__/
  inputs/*.pdf, inputs/*.json          *.pyc
  .env.example (safe template)         .coverage
  outputs/.gitkeep (empty dir marker)
```

### Why `outputs/` is gitignored but `.gitkeep` is not

The `outputs/` directory is gitignored because everything in it is generated by the pipeline — you can always reproduce it. But if the directory doesn't exist when someone clones the repo, the pipeline would fail trying to write `outputs/schema.json`.

The `.gitkeep` trick: add a zero-byte file inside `outputs/` and tell `.gitignore` to not ignore it (`!outputs/.gitkeep`). Now Git tracks the directory skeleton without tracking the generated contents.

### Typical development workflow

```bash
# Start a new feature
git checkout -b feature/add-fhir-extractor

# Make changes, run tests
pytest
ruff check src/

# Stage only the source files you changed (never stage .env or venv)
git add src/form_filler/extractors/fhir.py
git add tests/test_fhir_extractor.py
git add src/form_filler/cli.py     # updated composition root

# Commit with a clear message
git commit -m "Add FHIRExtractor for HL7 patient records"

# Push and open a PR
git push origin feature/add-fhir-extractor
# Open PR on GitHub → CI runs automatically
```

### What happens when you push

1. GitHub receives the push
2. **CI triggers** (`.github/workflows/ci.yml`):
   - `lint` job: runs `ruff check` on all Python files
   - `test` job: runs `pytest` with coverage
   - `docker` job: builds the image (only if lint + test pass)
3. If all green → merge is allowed
4. If any red → fix the issue, push again, CI re-runs

### Branch strategy

```
main          ← always deployable; CI must pass to merge
feature/*     ← development branches, opened as PRs
```

The CI pipeline acts as a **gate**: nobody can merge broken code to `main`.

### Why `inputs/` is committed but `outputs/` is not

`inputs/` contains the source documents — they are the problem data. They should be versioned so the pipeline is reproducible: anyone who clones the repo can run it and get the same `outputs/`.

`outputs/` is regenerated on every run. Committing it would cause noisy diffs (binary PDFs change checksums) and false history — you'd be tracking the *result* of running the code, not the code itself.

---

## 8. CI/CD pipeline explained

```yaml
# .github/workflows/ci.yml (simplified)

on: [push, pull_request]   # runs on every push and PR

jobs:
  lint:                     # job 1: code style
    - pip install ruff
    - ruff check src/ tests/

  test:                     # job 2: unit tests
    - pip install -e ".[dev]"
    - pytest --cov=src/form_filler --cov-report=xml
    - upload coverage to Codecov

  docker:                   # job 3: build check
    needs: [lint, test]     # only runs if both previous jobs pass
    - docker build -t form-filler:ci .
```

**Why this order matters:**
- Lint is cheapest (seconds) → catches typos fast
- Tests are medium (5–10s here) → catches logic bugs
- Docker build is slowest → only attempted when code is known-good

**In a production setup** you'd add a fourth step:
```yaml
  deploy:
    needs: [docker]
    if: github.ref == 'refs/heads/main'   # only on main branch
    - docker push registry/form-filler:latest
    - kubectl rollout restart deployment/form-filler
```

---

## 9. Interview talking points

### "Walk me through this project"

*"It's a pipeline that automates medical form population. The interesting engineering challenge wasn't the extraction itself — it was making it reliable. Every answer is traceable to a source document, and the system prefers leaving a field blank over guessing. I split the extraction into three sources ranked by confidence: structured JSON (0.95), clinical notes (0.75 with deterministic-first + evidence-gated LLM fallback), and lab PDF (0.70). The reconciler picks the highest-confidence value when sources conflict."*

### "Why SOLID?"

*"The original code had one 749-line class doing everything. By applying Single Responsibility, I split it into classes that each own exactly one source. Open/Closed means adding a new data source is one new file and one line in cli.py — no existing code changes. Dependency Inversion means Pipeline depends on `List[BaseExtractor]`, so in tests I pass mocks. The tests run in 5 seconds with no real PDFs or GPU needed."*

### "How do you prevent hallucination?"

*"Three layers: first, deterministic-first — regex over the Assessment section before touching the LLM. Second, completion-only — only ask the LLM for fields still missing; never re-query known fields. Third, evidence gating — every LLM output must include a verbatim quote from the source document; if the quote isn't found in the text, the extraction is discarded. Plus dose fields require a numeric value — purely symbolic validation that catches a common hallucination pattern."*

### "How would you scale this?"

*"Right now it's a single-run CLI. To scale: put the pipeline behind a FastAPI endpoint, replace the local Qwen model with a hosted inference endpoint (or use a constrained decoding runtime for reliable JSON output), add a job queue (Celery / SQS) for concurrent form processing, and store answers.json in a database instead of the filesystem. The Docker container is already stateless — it reads from `/data/inputs` and writes to `/data/outputs` — so horizontal scaling is straightforward."*

### "Why not just use GPT-4 for everything?"

*"Three reasons: the take-home required local open-source models only. But even without that constraint: demographics.json is already structured — using an LLM there adds latency and hallucination risk with no benefit. For SOAP notes, deterministic extraction handles 70% of the fields; the LLM only handles the remaining noisy cases. Mixing both gives you the reliability of deterministic logic with the flexibility of AI where needed."*

### "What would you improve?"

*"More robust test coverage for the LLM path (currently 59% on soap.py — the LLM branch is only reachable with torch installed). I'd also add a golden test set — a handful of pre-filled forms to measure precision/recall as the pipeline evolves. And I'd replace the file-based output with a proper data layer so multiple pipeline runs don't overwrite each other."*
