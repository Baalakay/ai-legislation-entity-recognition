# Project Scaffolding & Initial Structure

## Directory Structure

- `/backend/`
  - `main.py` (entry point for backend API)
  - `ingestion/` (PDF upload and validation logic)
  - `ai_extraction/` (module for sending PDFs to AI model and handling responses)
  - `output/` (CSV generation and output logic)
  - `config/` (settings, environment variables)

- `/frontend/`
  - `src/` (React/TypeScript app source code)
    - `components/` (UI components)
    - `pages/` (main pages/views)
    - `api/` (frontend API calls)
    - `styles/` (Tailwind, ShadUI config)
  - `public/` (static assets)

- `/data/`
  - `Train/` (training data)
    - `/data/Train/lables_train.csv` (labels/answers for training PDFs)
  - `Test/` (testing data)
    - `/data/Test/lables_test.csv` (labels/answers for testing PDFs)
  - `AI Analyzing the Legislation and Extracting Data.pdf` (specification helper)

- `/memory-bank/` (project memory and documentation)
- `/docs/` (additional documentation, PRDs, architecture, etc.)

- `pyproject.toml`, `README.md`, `.gitignore`, etc. (project-level config and docs)

## Notes
- For the PoC, review/, admin/, and tests/ modules are omitted for simplicity.
- No code-based PDF-to-text extraction module is included; AI model receives PDFs directly.
- Each backend module is a placeholder for PoC logic and can be expanded as needed.
- Frontend is scaffolded for document upload and results display.
- Data and memory-bank directories are central to development and evaluation.
- Training and testing labels/answers are now stored in separate CSV files corresponding to each data folder.

# Development Environment Setup

## Python Backend
- Use Python 3.12+ (as supported by uv)
- All packages installed and managed via `uv` (no pip)
- Project dependencies specified in `pyproject.toml`
- Build backend: hatchling
- Linting/formatting: ruff
- Environment variables managed via `.env` or config files in `/backend/config/`

## Frontend
- Node.js (LTS version recommended)
- React + TypeScript
- Styling: Tailwind CSS, ShadUI
- Dependency management: npm or yarn (standard Node tools)
- Linting/formatting: Prettier, ESLint
- Environment variables via `.env` or frontend config

## Tooling & Reproducibility
- Optionally use a `.devcontainer/` or Dockerfile for consistent dev environments
- Version control: Git (with `.gitignore` for Python, Node, and data artifacts)
- Recommended: VS Code or Cursor IDE for development

## Quickstart (example)
- `uv venv` to create and activate Python virtual environment
- `uv pip install -r requirements.txt` (if requirements file is used for quick setup)
- `uv pip sync` to ensure all dependencies match `pyproject.toml`
- `npm install` or `yarn` in `/frontend/` to set up frontend dependencies

## Notes
- All Python and Node dependencies should be documented and versioned
- No pip usage for Python; all backend dependencies via uv
- Use environment files for secrets/configuration, not hardcoded values

## Devcontainer
- The project is developed and run inside a **standard devcontainer** environment.
- All setup, tooling, and configuration should assume the devcontainer as the default context for development and execution.

# Workflow Plan: Chunking & Vision LLM Extraction

## Overview
This workflow enables robust extraction of metadata, disposition actions, and special flags from legislative PDFs of varying formats (text, scanned, hybrid) using a vision-capable LLM (e.g., Claude 3 Opus, GPT-4 Vision, Gemini).

## Step 1: PDF Chunking
- Split each PDF into manageable chunks to fit within the LLM's context window.
- **Recommended chunk size:** 1–2 pages per chunk (adjusted due to large images and typical document length of 3–12 pages).
- **Rationale:** Large images can consume significant context window space, so smaller chunks ensure reliable processing and avoid truncation.
- **Chunking method:**
  - By page range (default, simplest)
  - Optionally by logical section (if document structure is known)
- Each chunk is saved as a separate PDF file, retaining original page numbers for traceability.

## Step 2: Sending Chunks to the Vision LLM
- For each chunk, send the PDF (not extracted text) to the LLM via its API or interface.
- **Prompt Template:**
  > "You are an expert legislative document analyst. The following PDF chunk may contain text, images, or scanned pages. Please extract all required metadata, disposition actions (Add, Amend, Repeal, NCM), and special content flags, regardless of whether the information is in text or in an image/scan. Output the results as a CSV row with the following columns: [list columns]. If any required information is missing or illegible, note it as 'MISSING'."
- Ensure the prompt lists all required columns as specified in the project requirements.

## Step 3: Aggregation & Post-Processing
- Collect the LLM's output for each chunk.
- Tag each output with the chunk/page range for traceability.
- Aggregate all rows into a single CSV for the document.
- Deduplicate and resolve cross-references as needed (e.g., if the same action appears in multiple chunks).
- If any required fields are marked as 'MISSING', optionally flag for manual review.

## Step 4: Error Handling & Quality Control
- If the LLM output is incomplete, malformed, or missing, retry with a smaller chunk size or rephrase the prompt.
- Log all errors and outputs for traceability.
- Maintain a mapping from output rows to original chunk/page numbers for auditability.

## Notes
- This workflow assumes the LLM can process both text and image content in PDFs.
- For documents with highly variable formats, consider manual chunk review or user-guided chunking as a fallback.
- **All prompts and extraction logic must leverage the cues, patterns, and example phrases from the specification helper PDF (AI Analyzing the Legislation and Extracting Data.pdf) to maximize accuracy for all data attributes.**
- This plan is recorded in activeContext.md for ongoing reference and iteration.

# Workflow Plan: Textract + Bedrock LLM Integration

## Overview
This plan describes how to process chunked legislative PDFs using Amazon Textract for OCR and a Bedrock LLM for structured data extraction, ensuring robust handling of both text and image-based content.

## Step 1: Chunking
- Split each legislative PDF into 1–2 page chunks (as implemented in chunk_pdf.py).

## Step 2: OCR with Amazon Textract
- For each chunked PDF:
  - Upload the chunk to Amazon Textract via API or AWS Console.
  - Extract all text (and optionally tables/forms) from the chunk.
  - Save the extracted text for each chunk (e.g., as a .txt file or in memory).

## Step 3: LLM Extraction with Bedrock
- For each chunk's extracted text:
  - Send the text to your chosen Bedrock LLM (e.g., Claude 3, Llama 3) via the Bedrock API.
  - Use a prompt that instructs the LLM to extract all required metadata, disposition actions, and flags, referencing the cues/patterns from your specification helper PDF.
  - Collect the LLM's output (CSV row, JSON, etc.).

## Step 4: Aggregation & Post-Processing
- Aggregate the outputs from all chunks for the original document.
- Deduplicate, resolve cross-references, and flag any missing or ambiguous fields for manual review.

## Step 5: Error Handling & Logging
- Log all Textract and LLM API responses for traceability.
- If Textract or the LLM fails on a chunk, retry or flag for manual review.

## Step 6: (Optional) Automation
- Optionally, automate the entire pipeline (chunking → Textract → LLM → aggregation) as a batch process or serverless workflow.

# Active Context (as of latest update)

- The pipeline now uses a specification-aligned LLM prompt to extract only the required fields for Index.csv:
  - LEGNO, STATE, LEGTYPE, ADOPTION_DATE, CHAPTER/TITLE, LONG_TITLE, LONG_TITLE_SUMMARY, ARTICLE, SECTION, ACTION_CLASSIFICATION, DISPOSITION
- Output is structured for easy CSV export, with only the requested fields and no extraneous data.
- The prompt references the specification PDF for cues and patterns.
- The system no longer attempts to extract text styles (strikethrough, underlined, red text).
- All code and prompt logic is aligned with the projectbrief.md and the specification document.
- The output is robust to LLM formatting errors and is ready for further downstream integration or export.

# Pipeline Usage Update (2025-04-06)

- The only supported pipeline for document extraction is now `src/pipeline.py`, which uses the LLM's vision capabilities directly on PDF/image chunks.
- The previous Textract + Bedrock LLM pipeline (`src/textract_llm_pipeline.py`) is deprecated and should not be used.
- To run the pipeline, always provide a directory path (e.g., `data/Train/Amends/`) to `src/pipeline.py`. Do not provide a single PDF file; the script expects a folder and will process all relevant files within it.

# Prompt & Output Logic Update (2025-04-06)

- The LLM prompt now enforces a strict output field order: CITY/TOWN, STATE, LEGTYPE, LEGNO, ADOPTION_DATE, LONG_TITLE, LONG_TITLE_SUMMARY, ACTION_CLASSIFICATION, CHAPTER/TITLE, ARTICLE, SECTION, DISPOSITION, REDLINE.
- Redline detection is emphasized: if any page contains strikethrough (redline) text, the REDLINE field is set to 'X', regardless of color or font.
- Extraction rules are explicit: STATE and CITY/TOWN are only output if explicitly mentioned (never inferred); LEGNO, LEGTYPE, ADOPTION_DATE, CHAPTER/TITLE, LONG_TITLE, ARTICLE are only extracted from the first page/chunk; other fields follow detailed rules as in the prompt.
- Aggregation logic: for multi-page documents, results from all chunks are merged into a single record, deduplicating values case-insensitively, outputting in title case (except roman numerals, which are upper case), and reasoning as a senior legislation specialist to resolve conflicts.
- The prompt and output logic are versioned in prompt_versions.md, and all changes are tracked for reproducibility.

# Extraction Rules Update (2025-04-06)

- SECTION: Only extract if it is a clear section heading or title, not line numbers, page numbers, or metadata. If in doubt, leave blank.
- ADOPTION_DATE: Only extract valid dates in the current or previous century; ignore implausible or hallucinated values. Use the most recent plausible date if multiple are present.
- ACTION_CLASSIFICATION: Always classify as 'Amend' if there is any evidence of amendment (redline, strikethrough, or language indicating changes). Only use 'Add' if the document is clearly introducing new material. Prefer 'Amend' over 'Add' if in doubt.
- REDLINE: Only mark as 'X' if there is visible strikethrough or strikeout text; do not infer from context or language.
- STATE: Extract only if explicitly mentioned in the document text; search all pages. Do not infer from city/town or context. Use the value for the entire document if found on any page.

# Prompt & Extraction Rules Update (2025-04-07)

- The LLM prompt for REDLINE and ADOPTION_DATE is now simplified:
  - REDLINE: Mark as 'X' only if the text visually matches the attached example image (redline.jpg). No inference from context or language.
  - ADOPTION_DATE: Extract only if the date visually matches the attached example image (adoption_date_examples.jpg) and is clearly labeled as adopted, passed, approved, or enacted. No vote tallies, numbers in parentheses, or unrelated dates.
- This change is intended to improve LLM accuracy and consistency by reducing ambiguity and focusing on clear visual cues, rather than complex or redundant text instructions.
- All other extraction and aggregation rules remain unchanged from the previous version.

# Extraction Rules Update (2025-04-07)

- SECTION: Only extract if it is a clear section heading or title, not line numbers, page numbers, or metadata. If in doubt, leave blank.
- ADOPTION_DATE: Only extract valid dates in the current or previous century; ignore implausible or hallucinated values. Use the most recent plausible date if multiple are present.
- ACTION_CLASSIFICATION: Always classify as 'Amend' if there is any evidence of amendment (redline, strikethrough, or language indicating changes). Only use 'Add' if the document is clearly introducing new material. Prefer 'Amend' over 'Add' if in doubt.
- REDLINE: Only mark as 'X' if there is visible strikethrough or strikeout text; do not infer from context or language.
- STATE: Extract only if explicitly mentioned in the document text; search all pages. Do not infer from city/town or context. Use the value for the entire document if found on any page.

- The REDLINE extraction rule in the LLM prompt now references a visual example image (data/prompt_hints/redline.jpg) to clarify what counts as visible strikethrough/redline text.
- This is intended to improve LLM accuracy and consistency in detecting true redline/strikethrough, reducing false positives and ambiguity.
- All other extraction and aggregation rules remain unchanged from the previous version. 