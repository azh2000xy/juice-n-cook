#!/usr/bin/env python3
"""
OCR 管道脚本 — 将扫描版 PDF 转为结构化 Markdown 食谱

需要：
  1. Tesseract OCR 已安装并加入 PATH
     Windows: 下载 https://github.com/UB-Mannheim/tesseract/releases
     安装时勾选 Chinese Simplified (chi_sim) 语言包
  2. Python 依赖: pip install PyMuPDF pytesseract Pillow pyyaml

用法:
  python ocr_pipeline.py <pdf_path> <output_dir> --type juice|cooking

示例:
  python ocr_pipeline.py "../菜谱pdf/蔬果汁轻断食.pdf" "../data/raw/juice_text/" --type juice
"""

import sys
import os
import json
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)

try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("Error: pytesseract/Pillow not installed. Run: pip install pytesseract Pillow")
    sys.exit(1)


def check_tesseract(tesseract_cmd="tesseract"):
    """Verify Tesseract is installed with Chinese support."""
    import subprocess
    try:
        result = subprocess.run([tesseract_cmd, "--list-langs"], capture_output=True, text=True)
        if "chi_sim" not in result.stdout:
            print("Warning: Chinese simplified (chi_sim) language not found in Tesseract.")
            print("Download from: https://github.com/tesseract-ocr/tessdata/blob/main/chi_sim.traineddata")
            print("Place in Tesseract's tessdata directory.")
            return False
        print(f"Tesseract OK. Languages: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print(f"Error: Tesseract not found at: {tesseract_cmd}")
        print("Install Tesseract from: https://github.com/UB-Mannheim/tesseract/releases")
        print("Or use --tesseract-path to specify the location of tesseract.exe")
        return False


def ocr_pdf(pdf_path: str, output_dir: str, start: int = 0, end: int = None,
            dpi: int = 200, lang: str = "chi_sim+eng", tesseract_cmd: str = "tesseract"):
    """
    Extract text from scanned PDF using OCR.

    Args:
        pdf_path: Path to scanned PDF
        output_dir: Output directory for OCR text
        start: First page (0-indexed)
        end: Last page (exclusive)
        dpi: Resolution for OCR (higher = better accuracy, slower)
        lang: Tesseract language string
    """
    # Configure Tesseract path
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count

    if end is None:
        end = total_pages
    end = min(end, total_pages)

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    all_text = []

    for i in range(start, end):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix)

        # Convert to PIL Image for pytesseract
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # OCR
        text = pytesseract.image_to_string(img, lang=lang)

        # Save individual page text
        out_file = output_dir / f"page_{i+1:04d}.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)

        all_text.append(f"\n{'='*60}\n=== PAGE {i+1}\n{'='*60}\n\n{text}")

        if (i - start + 1) % 10 == 0:
            print(f"  Progress: {i - start + 1}/{end - start} pages OCR'd")

    doc.close()

    # Save combined text
    combined_path = output_dir / "_combined.txt"
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write("".join(all_text))

    print(f"\nDone! OCR'd {end - start} pages to: {output_dir}")
    print(f"Combined file: {combined_path}")
    print(f"\nNext step: Feed the combined text to an AI for structuring into Markdown recipes.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="OCR pipeline for scanned PDF -> recipe text extraction"
    )
    parser.add_argument("pdf_path", help="Path to scanned PDF")
    parser.add_argument("output_dir", help="Output directory for OCR text")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--lang", type=str, default="chi_sim+eng")
    parser.add_argument("--tesseract-path", type=str, default="tesseract",
                       help="Path to tesseract.exe (e.g. D:\\E\\TOOL\\tesseract\\tesseract.exe)")

    args = parser.parse_args()

    if not check_tesseract(args.tesseract_path):
        sys.exit(1)

    ocr_pdf(args.pdf_path, args.output_dir, args.start, args.end, args.dpi, args.lang,
            tesseract_cmd=args.tesseract_path)
