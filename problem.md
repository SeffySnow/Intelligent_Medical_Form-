## 🌟 **Overview**

This challenge is designed for candidates with ~**2–4 years of experience in machine learning, NLP, or AI engineering**. It simulates a real-world scenario where you must build a **pragmatic, reliable, AI-assisted document understanding pipeline** under time constraints.

We are specifically evaluating:

- **AI Engineering**
    - Practical use of open-source models (LLMs, vision models, etc)
    - Prompt design, input/output constraints, validation
    - Strategies to reduce hallucination
    - Combining symbolic methods with model-based reasoning
- **System Design**
    - Pipeline design, modularity, fallbacks
    - Scoping decisions & realistic assumptions w/ trade-offs
    - Intermediate inspection & logging
    - Efficiency: response time and cost optimization

You may use **any open-source libraries and models** (Hugging Face, PyTorch, Tesseract, LayoutParser, OpenCV, pdfminer, etc.). You may also use an**y AI assistants** (ChatGPT, Cursor, Claude, etc.) **only** for coding support. **Do not use any closed APIs or hosted models for the pipeline itself.**

Clarity of thought, responsible use of AI, and structured decision-making matter far more than model sophistication.

You should aim for roughly **4-6 hours of focused work** (though you have 3-4 days to complete it at your convenience). This challenge is intentionally broad, but you are expected to **narrow the scope yourself** based on your time, and available resources, and strategy. 

## 📘 Challenge: AI-Assisted Medical Form Understanding & Population

You will build a minimal, end-to-end system that:

1. Extracts the **schema** of a medical form
2. Extracts relevant information from a bundle of patient documents
3. Generates a **confidence-aware mapping** from fields → answers
4. (optional) Populates the original form with extracted values
5. Includes a mini evaluation component demonstrating thoughtful testing

As noted, you are expected to **scope the project appropriately**. You will not be penalized for not handling every file or field—**what matters is how you decide what to focus on**.

### **📥 Input (what we provide):**

- You will be working with two versions of the same single‑page medical form. Each version may require a different technical approach. Please experiment with both files. It’s fine if you don’t arrive at a complete solution for both—what matters most is how you explore and reason through the problem.
    - `form_fillable.pdf` - fillable PDF
    - `form_scanned.pdf` - scan of the same form
- Patient doc samples:
    - `demographics.json` - structured patient info
    - `soap_note.txt` - short noisy clinical note (typos, shorthand)
    - `lab_result.pdf` - scan of a medical test result for a patient (this document can be anything; e.g., a referral letter, blood test result, etc). So do not overfit your solution to this one particular document.)

---

[all_files.zip](attachment:d38e1ca3-09a2-4e4f-a6b3-42c41f424295:all_files.zip)

[form_fillable.pdf](attachment:52c69e5f-7fa3-4005-bc73-d2967fd063e1:form_fillable.pdf)

[form_scanned.pdf](attachment:8cf3749d-4934-4407-9f17-da02fbc90e11:form_scanned.pdf)

[lab_result.pdf](attachment:4c7cb3b8-b2b4-4ae4-98c0-f4e9baf5b458:lab_result.pdf)

[demographics.json](attachment:510efee4-f7f2-427a-b12f-631d99f09c97:demographics.json)

[soap_notes.txt](attachment:82c085f8-f9d6-4018-b645-81e4c8e83785:soap_notes.txt)

---

### **🚀 Your Tasks**

1. **Field Schema Extraction**
    
    Your system must produce a schema describing fields such as:
    
    ```json
    {
      "patient_name": {
        "label": "Patient Name",
        "type": "text",
        "bbox": [ ... ],
        "normalized_name": "patient_name"
      },
      ...
    }
    ```
    
    You may use any combination of:
    
    - PDF form metadata (fillable fields)
    - OCR + layout parsing
    - LLM-based inference of field names, types, normalization
    - Heuristics or regex-based fallbacks
    
    We want to see how you use AI **judiciously**, not excessively.
    
2. **AI-Assisted Information Extraction**
    
    For **at least** 5 form fields (more if you can), extract answers from the patient documents.
    
    - Determine which documents may contain answers
    - Extract candidate values
    - Use **AI models** for at least one of:
        - digesting noisy information
        - extracting answers
        - reasoning about noisy text
        - identifying missing information
        - mapping extracted text to canonical field types
        - deciding which source is most reliable
    
    You may also:
    
    - Add heuristics (e.g., DOB must be a date)
    - Add sanity checks
    - Cross-validate across documents
3. **Reconciliation, Validation & Confidence Estimation**
    
    Your final answers should include source citation and some form of reasoning. For example:
    
    ```json
    {
      "dob": {
        "value": "1978-10-05",
        "source": "demographics.json",
        "reasoning": "...",
        "confidence": 0.92
        }
    }
    ```
    
    Confidence estimation does **not** need to be sophisticated, but it must be **explained**. Examples:
    
    - source ranking
    - LLM self-reported confidence (with caveats)
4. **(Optional) PDF Population**
    
    Use the extracted answers to generate:
    
    - `populated.pdf`
    
    Populate only the fields your pipeline supports—do **not** hardcode field names.
    
5.  **Mini Evaluation Component (Required)**
    
    *Any simple evaluation* that demonstrates your engineering instincts.
    
    Examples:
    
    - test extraction accuracy on synthetic examples
    - compare LLM-extracted values to ground truth (manually written)
    - measure formatting consistency (e.g., are dates normalized?)
    - perform a hallucination check on SOAP note processing
    
    We’re not looking for high statistical rigor—just sound thinking.
    

### 📦 **Deliverables**

1. **`main.ipynb`**
    
    This is your solution which should be runnable standalone. It must include all the steps it took you to reach a solution, including the roadblocks you may have hit. It should also include intermediate printouts or visualization along with Markdown cells and comments. This code should include the following outputs:
    
    1. **`schema.json`** 
    2. **`answers.json`**
    3. **(optional) `populated.pdf`**
2. **`README.md` (1–3 pages)**
    
    Must include:
    
    - why this matters (your understanding of the problem)
    - your scope (what you chose to solve and why)
    - pipeline architecture & design decisions
    - where/why/how AI was used
    - prompt strategies or model selection
    - evaluation summary
    - key challenges
    - next steps if you had more time/resources

### 🗒️ Additional Notes

- If you hit a roadblock with an approach, document it and include it in your report
- If you encounter points of ambiguity, make reasonable assumptions and move forward. Include these assumptions in your report along with your reasoning

### 🔗 Additional Resources (Optional to Explore)

- [deepseek-ai/DeepSeek-OCR](https://huggingface.co/deepseek-ai/DeepSeek-OCR)
- [Google’s Tesseract-OCR Engine](https://github.com/tesseract-ocr/tesseract)
- [Vision Language Models](https://huggingface.co/blog/vlms)
- [LayourParser](https://github.com/Layout-Parser/layout-parser)

### ⚙️ **Constraints & Expectations**

- No multi-day model training or large fine-tuning
- Must run locally or on Google Colab
- Prefer a working end-to-end slice over a partially implemented large design even if results are not perfect
- Avoid hardcoding information (if you do so for experimental purposes, explicitly mention that)
- Responsible AI use matters (e.g., prevent hallucinations, validate model outputs)
- Your pipeline should only rely on **open‑source** models and libraries that can run locally or in Colab.

### 🎯 What We Are Evaluating

- The **engineering**, not the sophistication
- How you **scope**, **reason**, **validate**, and **structure**
- Balance between **deterministic** and **AI-assisted** methods
- Understanding of hallucination risks
- Ability to produce a **clean, reproducible pipeline**
- Clear communication and documentation in the `README.md`