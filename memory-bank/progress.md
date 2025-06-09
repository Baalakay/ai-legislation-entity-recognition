# Project Progress

## Current State
- START phase is complete.
- Memory bank is fully initialized with project brief, technology context, architecture, scaffolding, and environment setup.
- Project is running in a standard devcontainer.

## What Works
- All core requirements, goals, and constraints are documented.
- Technology stack and architecture are defined and recorded.
- Directory structure and environment setup are established for PoC.
- Data sources, training/testing data, and output schema are referenced in memory.

## Next Steps
- Transition to DEVELOPMENT phase using the RIPER workflow.
- Begin implementation of backend and frontend scaffolding.
- Integrate AI extraction logic for direct PDF processing.
- Set up CSV output generation and minimal UI for uploads/results.
- Iteratively test with provided training and testing data.

# Progress Update (latest)

- Refactored pipeline to use a concise, specification-driven LLM prompt.
- Only the required fields for Index.csv are extracted: LEGNO, STATE, LEGTYPE, ADOPTION_DATE, CHAPTER/TITLE, LONG_TITLE, LONG_TITLE_SUMMARY, ARTICLE, SECTION, ACTION_CLASSIFICATION, DISPOSITION.
- Output is clean, deduplicated, and ready for CSV export.
- All unnecessary fields and text-style detection have been removed.
- The system is robust to LLM formatting errors and is ready for further integration and testing.

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