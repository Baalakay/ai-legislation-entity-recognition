# Technology Context

## Core Technologies

### Backend
- **Language:** Python
- **Package Management:** 
  - Use `uv` for package management
  - Explicitly forbidden: pip
- **Build System:** hatchling
- **Code Quality:**
  - Linter/Formatter: ruff
  - Follow Python core best practices
  - Adhere to documentation standards
  - Apply single responsibility principle
- **OCR Service:**
  - **Amazon Textract** for extracting text from scanned/image-based and hybrid PDFs before LLM processing

### Frontend
- **Framework:** React
- **Language:** TypeScript
- **Styling:** 
  - Tailwind CSS
  - ShadUI component library

## Required Capabilities

### Document Processing
- PDF document parsing and analysis
- Chunking into 1–2 page segments
- OCR using Amazon Textract for both text-based and image-based PDFs
- Text extraction and pattern matching
- Metadata extraction
- Special instance detection

### Data Processing
- Batch processing support
- CSV output generation
- Data validation and verification

### System Requirements
- Process single document in under 2 minutes
- Support for batch processing
- 85%+ accuracy in metadata extraction
- 80%+ accuracy in disposition identification
- Secure document handling
- No persistent storage of sensitive content

## Development Environment
- Python environment managed by uv
- Modern development tools supporting TypeScript and React
- Version control (assumed Git)
- Development containers supported

## Dependencies Management
- All Python packages must be installed via uv
- Frontend dependencies managed via standard Node.js tools
- Maintain clear dependency documentation
- Regular updates for security and performance

## Security Considerations
- Implement data privacy requirements
- Secure document processing
- Limited document storage duration
- Access control for system functions

## Data Processing Flow
- PDF → Chunking → **Textract OCR** → LLM Extraction → Output 