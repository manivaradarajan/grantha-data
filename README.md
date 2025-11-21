# Quick Start: PDF-OCR

This tool uses Google's Gemini models to perform OCR on PDF documents.

## 1\. Installation

You can install the tool directly from GitHub using `pip`. We recommend doing this inside a virtual environment.

```bash
# (Optional but recommended) Create a clean environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install directly from GitHub
pip install git+https://github.com/manivaradarajan/grantha-data.git
```

## 2\. Setup API Key

You need a **Google Gemini API Key** to run the tool.
[Get an API Key here](https://aistudio.google.com/app/apikey).

**Mac/Linux:**

```bash
export GEMINI_API_KEY="your_api_key_here"
```

**Windows (PowerShell):**

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

## 3\. Usage

The installation adds the `pdf-ocr` command to your terminal.

```bash
$ pdf-ocr --help
usage: pdf-ocr [-h] [--pages-per-chunk PAGES_PER_CHUNK] [--max-chunks MAX_CHUNKS]
               [--start-page START_PAGE] [--num-pages NUM_PAGES] [--output-dir OUTPUT_DIR]
               [--workdir WORKDIR] [--model MODEL] [--clear-upload-cache] [--no-upload-cache]
               [--force-resplit] [--verbose]
               input_pdf

Extract structured Sanskrit text from PDF using Gemini OCR

positional arguments:
  input_pdf             Path to input PDF file

options:
  -h, --help            show this help message and exit
  --pages-per-chunk PAGES_PER_CHUNK
                        Number of pages per chunk (default: 10)
  --max-chunks MAX_CHUNKS
                        Maximum number of chunks to process (useful for testing)
  --start-page START_PAGE
                        Starting page number (1-indexed, default: 1)
  --num-pages NUM_PAGES
                        Number of pages to process from start-page (default: None [all])
  --output-dir OUTPUT_DIR
                        Output directory for extracted text (default: ocr_output)
  --workdir WORKDIR     Working directory for PDF chunks (default: pdf_ocr_workdir in current
                        directory)
  --model MODEL         Gemini model to use (default: gemini-2.5-pro)
  --clear-upload-cache  Clear expired entries (>48h old) from upload cache before processing
  --no-upload-cache     Disable upload caching (always upload fresh files)
  --force-resplit       Force re-splitting PDF even if cached chunks exist
  --verbose             Enable verbose logging

Examples:
  # Basic usage - process PDF with default settings
  pdf-ocr document.pdf

  # Custom chunk size and output directory
  pdf-ocr document.pdf --pages-per-chunk 15 --output-dir results/

  # Process only first 3 chunks for testing
  pdf-ocr document.pdf --max-chunks 3

  # Process specific page range (pages 20-30)
  pdf-ocr document.pdf --start-page 20 --num-pages 10

  # Process 5 pages starting from page 1
  pdf-ocr document.pdf --num-pages 5

  # Clear expired upload cache before processing
  pdf-ocr document.pdf --clear-upload-cache

  # Force re-upload (ignore upload cache)
  pdf-ocr document.pdf --no-upload-cache
```
