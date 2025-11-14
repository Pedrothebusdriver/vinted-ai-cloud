from pathlib import Path

import cv2
import pytesseract


class OCR:
    def read_text(self, image_path: Path) -> str:
        img = cv2.imread(str(image_path))
        if img is None:
            return ''
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        return pytesseract.image_to_string(gray, config='--psm 6')

    def extract_brand_size(self, text: str):
        t = text.upper()
        brand = None
        size = None
        for key in [
            'NIKE','ADIDAS','ZARA','H&M','NEXT','LEVIS','LEVI','PUMA',
            'NORTH FACE','UNIQLO','PRIMARK','M&S','M AND S','HOLLISTER',
            'TOMMY','RALPH','LACOSTE','NEW LOOK','ASOS','RIVER ISLAND'
        ]:
            if key in t:
                brand = key
                break
        import re
        m = re.search(r'\b(XXS|XS|S|M|L|XL|XXL|\d{2})\b', t)
        if m:
            size = m.group(1)
        conf_b = 'High' if brand else 'Low'
        conf_s = 'High' if size else 'Low'
        return brand, conf_b, size, conf_s
