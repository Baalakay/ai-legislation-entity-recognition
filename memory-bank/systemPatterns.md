# System Architecture: Legislative Document Analysis System

## Overview
A modular, AI-powered pipeline for automating the extraction and analysis of legislative documents, supporting code maintenance workflows with structured outputs and high accuracy.

## Major Components
- **Document Ingestion Service**
  - Accepts PDF documents from users or batch uploads
  - Validates file format and integrity
- **Chunking Module**
  - Splits each PDF into 1–2 page chunks for manageable processing
- **OCR Service (Amazon Textract)**
  - Receives each PDF chunk and extracts all text (and optionally tables/forms) from both text and image content
  - Outputs plain text for each chunk, which is then sent to the LLM
- **LLM Extraction Engine**
  - Receives extracted text from Textract
  - Uses LLM to interpret, extract, and analyze all required metadata, dispositions, and content flags
- **Output Generator**
  - Produces structured CSV output per document/disposition
  - Ensures output matches schema in `lables_train.csv`/`lables_test.csv`
- **Review & Exception Handler**
  - Flags documents requiring manual review
  - Provides interface for human-in-the-loop corrections
- **Frontend Interface**
  - React/TypeScript web UI for document upload, review, and results
  - Displays processing status and output summaries
- **Admin & Monitoring Tools**
  - System health, job tracking, and error reporting

## Data Flow
1. User uploads PDF (via frontend or batch)
2. Ingestion Service validates and stores the document
3. Chunking Module splits the PDF into 1–2 page chunks
4. **OCR Service (Textract)** processes each chunk, extracting all text
5. LLM Extraction Engine receives the extracted text and performs all extraction/analysis
6. Output Generator writes results to CSV
7. Review Handler flags/queues exceptions for manual review
8. Frontend displays results and review queue

## Integration Points
- **Amazon Textract**: Used for OCR on each PDF chunk before LLM extraction
- **Legislation Specifications Helper**: Used by LLM extraction/analyzer modules for pattern matching
- **Training Data**: `/data/Train/` for model development
- **Testing Data**: `/data/Test/` for evaluation
- **Output Schema**: `/data/Train/lables_train.csv` and `/data/Test/lables_test.csv` define required output columns and flags

## Security & Compliance
- All document uploads are validated and sanitized
- No persistent storage of sensitive content beyond processing period
- Access controls for admin and review functions
- Compliance with data privacy requirements

## Extensibility
- Modular pipeline allows for future enhancements (e.g., new jurisdictions, additional output formats, improved ML models)
- Clear separation of concerns between ingestion, OCR, extraction, analysis, and output

## PoC Note
- For the proof of concept, all PDFs are processed through Amazon Textract for OCR before LLM extraction to ensure both text and image-based content are handled robustly. 