#!/usr/bin/env python3
"""
PDF 页面转图片工具
将扫描版 PDF 逐页转为 PNG 图片，便于后续 OCR 或视觉识别。

用法: python pdf_to_images.py <pdf_path> <output_dir> [--start N] [--end N] [--dpi 200]
"""

import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Run: pip install PyMuPDF")
    sys.exit(1)


def pdf_to_images(pdf_path: str, output_dir: str, start: int = 0,
                  end: int = None, dpi: int = 200):
    """
    Convert PDF pages to PNG images.

    Args:
        pdf_path: Path to the PDF
        output_dir: Output directory for images
        start: First page (0-indexed)
        end: Last page (exclusive, None = all)
        dpi: Resolution for rendering (default 200)
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total_pages = doc.page_count
    print(f"PDF: {pdf_path.name}")
    print(f"Pages: {total_pages}")

    if end is None:
        end = total_pages
    end = min(end, total_pages)

    # Calculate zoom factor from DPI (default PDF DPI is 72)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    for i in range(start, end):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix)
        out_file = output_dir / f"page_{i+1:04d}.png"
        pix.save(str(out_file))

        if (i - start + 1) % 10 == 0:
            print(f"  Progress: {i - start + 1}/{end - start} pages")

    doc.close()
    print(f"\nDone! Saved {end - start} pages to: {output_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert PDF pages to PNG images")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("output_dir", help="Output directory for images")
    parser.add_argument("--start", type=int, default=0, help="Start page (0-indexed)")
    parser.add_argument("--end", type=int, default=None, help="End page (exclusive)")
    parser.add_argument("--dpi", type=int, default=200, help="Render DPI (default 200)")

    args = parser.parse_args()
    pdf_to_images(args.pdf_path, args.output_dir, args.start, args.end, args.dpi)
