import sys
from pathlib import Path
from pypdf import PdfReader, PdfWriter

def chunk_pdf(input_pdf_path, output_dir, chunk_size=2):
    """
    Split a PDF into smaller PDFs, each containing up to chunk_size pages.
    Args:
        input_pdf_path (str or Path): Path to the input PDF file.
        output_dir (str or Path): Directory to save the chunked PDFs.
        chunk_size (int): Number of pages per chunk (default: 2).
    """
    input_pdf = PdfReader(str(input_pdf_path))
    num_pages = len(input_pdf.pages)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for start in range(0, num_pages, chunk_size):
        end = min(start + chunk_size, num_pages)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(input_pdf.pages[i])
        chunk_filename = output_dir / f"{Path(input_pdf_path).stem}_pages_{start+1}-{end}.pdf"
        with open(chunk_filename, "wb") as f:
            writer.write(f)
        print(f"Created chunk: {chunk_filename}")

if __name__ == "__main__":
    """
    Usage:
        python chunk_pdf.py <input_pdf> <output_dir> [chunk_size]
    Example:
        python chunk_pdf.py /workspace/data/Train/Repeals/2344152.pdf /workspace/data/Train/Repeals/chunks 2
    """
    if len(sys.argv) < 3:
        print("Usage: python chunk_pdf.py <input_pdf> <output_dir> [chunk_size]")
        sys.exit(1)
    input_pdf = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    chunk_size = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    chunk_pdf(input_pdf, output_dir, chunk_size) 