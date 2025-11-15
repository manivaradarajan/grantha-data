#!/bin/bash
# Helper script to check and set GEMINI_API_KEY

if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ GEMINI_API_KEY is not set"
    echo ""
    echo "To set it:"
    echo "  1. Get your API key from: https://aistudio.google.com/app/apikey"
    echo "  2. Run: export GEMINI_API_KEY=\"your-api-key-here\""
    echo ""
    echo "Or run the converter with the key inline:"
    echo "  GEMINI_API_KEY=\"your-key\" python convert_meghamala.py -i input.md -o output.md ..."
    exit 1
else
    KEY_LEN=${#GEMINI_API_KEY}
    echo "✅ GEMINI_API_KEY is set (length: $KEY_LEN characters)"
    echo ""
    echo "You can now run:"
    echo "  python convert_meghamala.py -i input.md -o output.md --grantha-id id --canonical-title \"Title\""
fi
