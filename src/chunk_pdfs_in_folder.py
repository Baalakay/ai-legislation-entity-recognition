import os
import sys
from pathlib import Path
import shutil
from pypdf import PdfReader, PdfWriter

def clean_chunks_folders(root_folder):
    root = Path(root_folder)
    for parent in root.rglob(""):
        if parent.is_dir():
            chunks = parent / "chunks"
            if chunks.exists():
                shutil.rmtree(chunks)


def chunk_pdf(input_pdf_path, output_dir):
    input_pdf = PdfReader(str(input_pdf_path))
    num_pages = len(input_pdf.pages)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_files = []
    for page_num in range(num_pages):
        writer = PdfWriter()
        writer.add_page(input_pdf.pages[page_num])
        chunk_filename = output_dir / f"{Path(input_pdf_path).stem}_{page_num+1}.pdf"
        with open(chunk_filename, "wb") as f:
            writer.write(f)
        print(f"Created chunk: {chunk_filename}")
        chunk_files.append(chunk_filename)
    return chunk_files

def chunk_folder(folder_path, recursive=True):
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"Error: {folder_path} is not a directory.")
        return
    clean_chunks_folders(folder)
    pdf_files = list(folder.rglob("*.pdf") if recursive else folder.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF(s) in {folder_path}")
    for pdf_file in pdf_files:
        # Skip files in any chunks subfolder
        if any(part == "chunks" for part in pdf_file.parts):
            continue
        chunks_dir = pdf_file.parent / "chunks"
        chunk_pdf(pdf_file, chunks_dir)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compress_pdfs_in_folder.py <folder_path> [--no-recursive]")
        sys.exit(1)
    folder_path = sys.argv[1]
    recursive = "--no-recursive" not in sys.argv
    chunk_folder(folder_path, recursive=recursive)