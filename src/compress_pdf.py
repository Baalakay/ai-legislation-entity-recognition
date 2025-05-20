import subprocess
import os

def compress_pdf(input_path, output_path, quality="ebook"):
    """
    Compress a PDF file using Ghostscript.
    
    Parameters:
        input_path (str): Path to the input PDF.
        output_path (str): Path to save the compressed PDF.
        quality (str): Compression quality. Options:
            - 'screen'  (lowest, smallest file)
            - 'ebook'   (good for e-readers, default)
            - 'printer' (high quality)
            - 'prepress' (highest quality)
    """
    # Ghostscript PDFSETTINGS options
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
        print(f"Compressed PDF saved to: {output_path}")
    except subprocess.CalledProcessError as e:
        print("Ghostscript compression failed:", e)

# Example usage:
if __name__ == "__main__":
    input_pdf = "data/Train/Repeals/2344152.pdf"
    output_pdf = "data/Train/Repeals/2344152_compressed.pdf"
    compress_pdf(input_pdf, output_pdf, quality="ebook")