import os
import io
import re
import base64
from PIL import Image
import google.generativeai as genai

# API 키 설정
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("환경변수 GEMINI_API_KEY가 설정되지 않았습니다.")

genai.configure(api_key=api_key)

model = genai.GenerativeModel("models/gemini-1.5-pro-vision")

def extract_company_and_article(image: Image.Image) -> dict:
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()

    prompt = (
        "You're analyzing a fabric swatch or textile specification sheet. "
        "Please extract the following:\n"
        "1. Company or brand name (e.g., 'ALLBLUE Inc.', 'COSMO TEXTILE', 'HK TEXTILE')\n"
        "2. Article number(s), typically in formats like: 'AB-EX171', 'BD3991', '1025-600-3', etc.\n\n"
        "🎯 Output ONLY in the following JSON format:\n"
        "{\n"
        "  \"company\": \"<Company Name>\",\n"
        "  \"article_numbers\": [\"<article1>\", \"<article2>\"]\n"
        "}\n\n"
        "If any value is not found, return 'N/A'."
    )

    try:
        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": image_bytes}
        ])
        text = response.text.strip()

        company_match = re.search(r'"company"\s*:\s*"([^"]+)"', text)
        article_matches = re.findall(r'"([A-Z0-9\-]{5,})"', text)

        company = company_match.group(1).strip() if company_match else "N/A"

        return {
            "company": company,
            "article_numbers": list(set(article_matches)) if article_matches else ["N/A"]
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

