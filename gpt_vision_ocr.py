
import openai
import base64
import io
import json
import re
import os
from PIL import Image
import pytesseract
from google.cloud import vision
from collections import Counter

openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 브랜드명 정규화
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    brand_map = {
        "HOKKOH": ["HKK", "HKH", "HKKH", "HOKKH"],
        "Uni Textile Co., Ltd.": ["UNI TEXTILE", "KOMON KOBO", "\u5c0f\u7d0b\u5de5\u623f"],
        "Ohara Inc.": ["OHARA", "OHARAYA"],
        "ALLBLUE Inc.": ["ALLBLUE"],
        "Matsubara Co., Ltd.": ["MATSUBARA"],
        "YAGI": ["YAGI"],
        "Vancet": ["VANCET"],
        "COSMO TEXTILE CO., LTD.": ["COSMO"],
        "DUCK TEXTILE CO., LTD.": ["ダック", "DUCK"]
    }
    for normalized, aliases in brand_map.items():
        for alias in aliases:
            if alias in name.upper():
                return normalized
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# ✅ 품번 유효성 필터
def is_valid_article(article: str, company=None) -> bool:
    article = article.strip().upper()
    invalid_keywords = ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]
    if article in invalid_keywords:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    if len(article) < 3 or not re.search(r"[A-Z0-9]", article):
        return False
    if article.startswith("HTTP") or ".COM" in article:
        return False
    if re.fullmatch(r"\d{3}", article):
        return False
    return bool(re.search(r"[A-Z0-9/\-]{3,}", article)) or bool(re.search(r"\d{3,}", article))

# ✅ 오탐 가능성 높은 품번 감지
def is_suspicious_article(article: str) -> bool:
    a = article.upper()
    return bool(re.search(r"(.)\1{2,}", a)) or bool(re.fullmatch(r"\d{2,3}[A-Z]{2,}X+\d{3}", a))

# ✅ OCR: Google Vision
def google_vision_ocr(image: Image.Image) -> str:
    client = vision.ImageAnnotatorClient()
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    content = buffered.getvalue()
    image_google = vision.Image(content=content)
    response = client.text_detection(image=image_google)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ✅ OCR: Tesseract
def tesseract_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang='eng')

# ✅ 이미지 리사이즈
def resize_image(image, max_size=(1600, 1600)):
    if image.width > max_size[0] or image.height > max_size[1]:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ 신뢰도 기반 품번 정렬
def get_high_confidence_articles(gpt_articles, google_articles, tesseract_articles):
    all_sources = {"GPT": gpt_articles, "Google": google_articles, "Tesseract": tesseract_articles}
    article_counts, article_sources = Counter(), {}

    for source, articles in all_sources.items():
        for a in articles:
            a_clean = a.strip().upper()
            article_counts[a_clean] += 1
            article_sources.setdefault(a_clean, set()).add(source)

    scored = []
    for article, count in article_counts.items():
        score = 0
        sources = article_sources[article]
        if "GPT" in sources: score += 3
        if "Google" in sources: score += 3
        if "Tesseract" in sources: score += 2
        if len(article) >= 6: score += 1
        if "-" in article or "/" in article: score += 1
        scored.append((article, score))

    scored.sort(key=lambda x: -x[1])
    return [a for a, s in scored if s >= 6][:5]

# ✅ GPT Vision 기반 추출
def gpt_ocr(image: Image.Image) -> dict:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    prompt_text = (
        "You are an OCR engine. Extract only visible text.\n"
        "Return only:\n"
        "1. Brand name\n2. Article numbers\n"
        "Strict format:\n{ \"company\": \"...\", \"article_numbers\": [\"...\"] }"
    )

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]
            }
        ],
        max_tokens=700,
    )
    result_text = response.choices[0].message.content.strip()
    try:
        return json.loads(result_text), False
    except json.JSONDecodeError:
        company_match = re.search(r'"?company"?\s*:\s*"([^"]+)"', result_text)
        raw_articles = re.findall(r'"([A-Z0-9/\-]{3,})"', result_text)
        return {
            "company": company_match.group(1).strip() if company_match else "N/A",
            "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
        }, True

# ✅ 메인 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        gpt_result, used_fallback = gpt_ocr(image)
        raw_company = gpt_result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        gpt_articles = gpt_result.get("article_numbers", [])
        gpt_articles = [a.strip().upper() for a in gpt_articles]

        google_articles = re.findall(r"[A-Z0-9/\-]{3,}", google_vision_ocr(image))
        tesseract_articles = re.findall(r"[A-Z0-9/\-]{3,}", tesseract_ocr(image))

        high_confidence = get_high_confidence_articles(gpt_articles, google_articles, tesseract_articles)

        filtered_articles = [
            a for a in high_confidence
            if is_valid_article(a, normalized_company)
            and not a.startswith("000")
            and not is_suspicious_article(a)
            and a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

        if not filtered_articles:
            fallback_articles = [
                a for a in gpt_articles
                if is_valid_article(a, normalized_company)
                and not is_suspicious_article(a)
            ]
            filtered_articles = fallback_articles[:3]

        return {
            "company": normalized_company if normalized_company else "N/A",
            "article_numbers": filtered_articles if filtered_articles else ["N/A"],
            "used_fallback": used_fallback
        }
    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"],
            "used_fallback": True
        }
