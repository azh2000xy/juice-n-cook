#!/usr/bin/env python3
"""
Phase 1: PDF 原始文本提取
从 PDF 中逐页提取文本，输出到 data/raw/ 目录。

用法: python extract_pdf.py <pdf_path> <output_dir> [--start N] [--end N]
示例: python extract_pdf.py "../菜谱pdf/蔬果汁轻断食.pdf" "../data/raw/juice/"
"""

import sys
import os
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("Error: pypdf not installed. Run: pip install pypdf")
    sys.exit(1)


def extract_pdf(pdf_path: str, output_dir: str, start: int = 0, end: int = None):
    """
    Extract text from PDF page by page.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to write extracted text files
        start: First page to extract (0-indexed, default 0)
        end: Last page to extract (0-indexed, exclusive, default all)
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening PDF: {pdf_path} ({pdf_path.stat().st_size / 1024 / 1024:.1f} MB)")
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    print(f"Total pages: {total_pages}")

    if end is None:
        end = total_pages
    end = min(end, total_pages)

    extracted_count = 0
    for i in range(start, end):
        page = reader.pages[i]
        text = page.extract_text()

        if text and text.strip():
            # Write page text to file
            out_file = output_dir / f"page_{i+1:04d}.txt"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(text)
            extracted_count += 1
        else:
            print(f"  Page {i+1}: [no text extracted - may be image-only]")

        # Progress indicator
        if (i - start + 1) % 20 == 0:
            print(f"  Progress: {i - start + 1}/{end - start} pages processed")

    print(f"\nDone! Extracted {extracted_count} pages with text to: {output_dir}")
    print(f"({end - start - extracted_count} pages had no extractable text)")

    # Also combine all pages into one file for easier AI processing
    combined_path = output_dir / "_combined.txt"
    with open(combined_path, "w", encoding="utf-8") as out:
        for i in range(start, end):
            page_file = output_dir / f"page_{i+1:04d}.txt"
            if page_file.exists():
                out.write(f"\n{'='*60}\n")
                out.write(f"=== PAGE {i+1}\n")
                out.write(f"{'='*60}\n\n")
                with open(page_file, "r", encoding="utf-8") as inf:
                    out.write(inf.read())
                out.write("\n")
    print(f"Combined file: {combined_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract text from PDF page by page")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("output_dir", help="Output directory for extracted text")
    parser.add_argument("--start", type=int, default=0, help="Start page (0-indexed)")
    parser.add_argument("--end", type=int, default=None, help="End page (exclusive)")

    args = parser.parse_args()
    extract_pdf(args.pdf_path, args.output_dir, args.start, args.end)
