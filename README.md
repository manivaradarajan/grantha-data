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
# Process a PDF
pdf-ocr path/to/document.pdf
```
