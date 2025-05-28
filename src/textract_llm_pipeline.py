import boto3
from pathlib import Path

# Initialize AWS clients (fill in your region and credentials as needed)
textract_client = boto3.client('textract')
bedrock_client = boto3.client('bedrock-runtime')  # For Bedrock LLM API

def textract_ocr(pdf_path):
    """
    Extracts text from a PDF file using Amazon Textract's synchronous API.

    Args:
        pdf_path (str or Path): Path to the PDF file chunk.

    Returns:
        str: The extracted text from the PDF.

    Raises:
        Exception: If Textract fails or the file is invalid.

    AWS Requirements:
        - Textract:DetectDocumentText permission
        - Credentials must be configured via environment or AWS profile

    Example:
        text = textract_ocr("/path/to/chunk.pdf")
        print(text)
    """
    from botocore.exceptions import BotoCoreError, ClientError
    import time

    if not Path(pdf_path).is_file():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    with open(pdf_path, "rb") as f:
        document_bytes = f.read()

    try:
        response = textract_client.detect_document_text(
            Document={"Bytes": document_bytes}
        )
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Textract OCR failed: {e}")

    # Extract text from Textract response
    lines = []
    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block["Text"])
    return "\n".join(lines)

def bedrock_llm_extract(text, prompt_template):
    """
    Calls Bedrock LLM with the extracted text and prompt.
    Returns the LLM's output (CSV row, JSON, etc.).
    """
    # TODO: Implement Bedrock LLM API call
    # Example: Use bedrock_client.invoke_model with the prompt and text
    return ""

def process_folder(chunks_folder, prompt_template, output_folder):
    """
    For each PDF chunk in the folder:
      1. Run Textract OCR
      2. Run LLM extraction
      3. Save results
    """
    chunks_folder = Path(chunks_folder)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    for pdf_chunk in chunks_folder.glob("*.pdf"):
        print(f"Processing: {pdf_chunk}")
        text = textract_ocr(pdf_chunk)
        llm_output = bedrock_llm_extract(text, prompt_template)
        # Save outputs (customize as needed)
        with open(output_folder / f"{pdf_chunk.stem}_extracted.txt", "w") as f:
            f.write(llm_output)

def main():
    # TODO: Parse arguments, set up prompt template, and call process_folder
    pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        print(f"Running Textract OCR on: {pdf_path}")
        try:
            text = textract_ocr(pdf_path)
            print("--- Extracted Text ---")
            print(text)
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python textract_llm_pipeline.py <pdf_chunk_path>") 