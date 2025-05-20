# Project Brief: Legislative Document Analysis System

## Purpose
Automate the analysis of legislative and ordinance documents using AI, extracting key metadata and determining if updates to legislative Code are required. The system is designed to support Code maintenance workers by streamlining and structuring the document review process.

## Project Goals
1. Automate extraction of key metadata (legislation type, number, adoption date, etc.) from legislative documents.
2. Accurately determine if a document requires updates to the legislative Code.
3. Identify the specific nature of changes required (Add, Amend, Repeal, NCM).
4. Flag Non-Code Material (NCM) and special instances requiring additional processing.
5. Generate structured outputs (CSV) summarizing all required Code changes for maintenance workflows.
6. Support batch processing, high accuracy, and scalability.

## Intended Users
- **Code Maintenance Workers:** Legal professionals responsible for updating municipal/state codes, requiring clear, structured information about required changes.
- **System Administrators:** Manage and monitor the system, handle exceptions, and ensure processing quality.

## Key Features
- Accepts PDF legislation documents from various jurisdictions and formats
- Extracts metadata and disposition actions (Add, Amend, Repeal, NCM)
- Detects special instances (e.g., nomenclature changes, redline text, missing attachments)
- Generates structured CSV output for each document and disposition
- Flags documents requiring manual review
- Meets performance and accuracy targets (processing time, extraction accuracy)
- Ensures security and privacy compliance

## Out of Scope / Limitations
- Will not process certain document types (e.g., MA towns, CT/NH/ME Town Meetings, Tribes, MD counties)
- Will not extract full text content of amendments/additions (focus is on metadata)
- Some documents will still require manual review due to complexity or uniqueness

## Success Metrics
- Accuracy of metadata and disposition extraction
- Processing speed per document
- Reduction in manual review workload
- User satisfaction from Code maintenance workers 

## Data Sources & Specifications
- **Legislation Specifications Helper Document:**
  - `/workspace/data/AI Analyzing the Legislation and Extracting Data.pdf` — Reference guide for legislative data extraction and specification patterns.
  - **All extraction logic and prompts must use the cues, patterns, and example phrases from this document to accurately identify and map data attributes (e.g., Leg Type, Disposition, etc.) regardless of phrasing or format.**
- **Training Data:**
  - `/workspace/data/Train/` — Labeled legislative documents for model training, organized by disposition type (Adds, Amends, NCM, Repeals).
  - `/workspace/data/Train/lables_train.csv` — Ground-truth answers/labels for the training PDFs.
- **Testing Data:**
  - `/workspace/data/Test/` — Labeled legislative documents for model evaluation, organized by disposition type (Adds, Amends, NCM, Repeals).
  - `/workspace/data/Test/lables_test.csv` — Ground-truth answers/labels for the testing PDFs. 

## Best Practices
- Extraction prompts and logic should reference the full range of possible phrasings and synonyms for each attribute, as documented in the specification helper PDF. 