import subprocess
import os
import sys
from pathlib import Path

def compress_pdf(input_path, output_path, quality="ebook"):
    quality_settings = {
        "screen": "/screen",
        "ebook": "/ebook",
        "printer": "/printer",
        "prepress": "/prepress"
    }
    gs_quality = quality_settings.get(quality, "/ebook")
    command = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={gs_quality}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_path}",
        input_path
    ]
    try:
        subprocess.run(command, check=True)
        print(f"Compressed: {input_path} -> {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to compress {input_path}: {e}")

def compress_folder(folder_path, quality="ebook", recursive=True):
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"Error: {folder_path} is not a directory.")
        return

    pdf_files = list(folder.rglob("*.pdf") if recursive else folder.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF(s) in {folder_path}")
    for pdf_file in pdf_files:
        output_file = pdf_file.with_name(pdf_file.stem + "_compressed.pdf")
        print(f"Compressing: {pdf_file} -> {output_file}")
        compress_pdf(str(pdf_file), str(output_file), quality=quality)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compress_pdfs_in_folder.py <folder_path> [quality] [--no-recursive]")
        sys.exit(1)
    folder_path = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "ebook"
    recursive = "--no-recursive" not in sys.argv
    compress_folder(folder_path, quality=quality, recursive=recursive)