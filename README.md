# Vinted AI Cloud (Pete)

Render-ready Flask API that analyses clothing photos:
- CLIP (FashionCLIP if available) for item type
- EasyOCR + fuzzy match for brand and size (adult + children)
- Returns ready-to-use listing JSON

## Local run
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
# -> http://127.0.0.1:10000/health

## Test
bash ./test_upload.sh
