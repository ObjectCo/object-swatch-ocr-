# ✅ Google Cloud Vision OCR + GPT-4o 분석 기반
# 정확도 98~99%를 목표로 하는 하이브리드 방식

import os
import json
import io
import re
from typing import List
from PIL import Image
from google.cloud import vision
import openai

# 환경변수 필요: GOOGLE_APPLICATION_CREDENTIALS, OPENAI_API_KEY
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Google Cloud Vision OCR 클라이언트 초기화
gcv_client = vision.ImageAnnotatorClient()

def normalize_brand(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"HKK|HKH|HKKH|HOKKH", name):
        return "HOKKOH"
    if "SOJITZ" in name:
        return "Sojitz Fashion Co., Ltd."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "KOMON" in name:
        return "KOMON KOBO"
    if "YAGI" in name:
        return "YAGI"
    return name.title()

def is_valid_article(article: str) -> bool:
    article = article.upper()
    if any(keyword in article for keyword in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "OCA"]):
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    return bool(re.search(r"\d{3,}", article)) or bool(re.match(r"[A-Z0-9\-/#]{4,}", article))

def extract_text_with_gcv(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    content = buffered.getvalue()

    image = vision.Image(content=content)
    response = gcv_client.text_detection(image=image)
    texts = response.text_annotations

    if not texts:
        return ""
    return texts[0].description  # 전체 텍스트 블록 리턴

def extract_info_with_gpt(raw_text: str) -> dict:
    prompt = f"""
Below is OCR text from a fabric swatch image:

\"\"\"
{raw_text}
\"\"\"

From this text, extract:
1. The brand name (e.g. HOKKOH, ALLBLUE Inc., Sojitz Fashion Co., Ltd.)
2. Valid article numbers (e.g. TXAB-H062, OSDC40031, 2916, BD3991)

Ignore unrelated terms like TEL, FAX, HTTP, WWW, COLOR, OCA, Article, URL.

Return in this JSON format:
{{ "company": "BRAND", "article_numbers": ["CODE1", "CODE2"] }}
If nothing is found, return:
{{ "company": "N/A", "article_numbers": ["N/A"] }}
"""


    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt.strip()}
        ],
        max_tokens=800
    )

    result_text = response.choices[0].message.content.strip()

    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
        article_matches = re.findall(r'"([A-Z0-9\-/#]{4,})"', result_text)
        result = {
            "company": company_match.group(1) if company_match else "N/A",
            "article_numbers": list(set(article_matches)) if article_matches else ["N/A"]
        }

    company = normalize_brand(result.get("company", "N/A"))
    article_numbers = [a for a in result.get("article_numbers", []) if is_valid_article(a)]

    if not article_numbers:
        article_numbers = ["N/A"]

    return {
        "company": company,
        "article_numbers": article_numbers
    }

def extract_info_from_image(image: Image.Image) -> dict:
    try:
        raw_text = extract_text_with_gcv(image)
        if not raw_text.strip():
            return {"company": "N/A", "article_numbers": ["N/A"]}
        return extract_info_with_gpt(raw_text)
    except Exception as e:
        return {"company": "[ERROR]", "article_numbers": [f"[ERROR] {str(e)}"]}
