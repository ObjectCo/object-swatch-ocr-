# ocr_engines.py
import base64
import io
import os
import openai
import pytesseract
import re
from PIL import Image
from google.cloud import vision

openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 이미지 리사이즈
def resize_image(image, max_size=(1600, 1600)):
    if image.width > max_size[0] or image.height > max_size[1]:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ Tesseract OCR
def tesseract_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang='eng')

# ✅ Google Vision OCR
def google_vision_ocr(image: Image.Image) -> str:
    client = vision.ImageAnnotatorClient()
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    content = buffered.getvalue()
    image_google = vision.Image(content=content)
    response = client.text_detection(image=image_google)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ✅ GPT OCR (Vision API)
def gpt_vision_ocr(image: Image.Image, prompt_text: str) -> dict:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

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
    return result_text

# postprocess.py
import re
import json
from typing import List, Tuple

# ✅ 브랜드명 정규화
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    replacements = {
        "HOKKH": "HOKKOH", "HKKH": "HOKKOH", "HKH": "HOKKOH", "HKK": "HOKKOH",
        "KOMON KOBO": "Uni Textile Co., Ltd.",
        "UNI TEXTILE": "Uni Textile Co., Ltd.",
        "OHARAYA": "Ohara Inc.",
        "OHARA": "Ohara Inc.",
        "ALLBLUE": "ALLBLUE Inc.",
        "MATSUBARA": "Matsubara Co., Ltd.",
        "YAGI": "YAGI",
        "VANCET": "Vancet"
    }
    for key, val in replacements.items():
        if key in name:
            return val
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# ✅ 품번 유효성 필터
def is_valid_article(article: str, company=None) -> bool:
    article = article.strip().upper()

    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    if len(article) < 3:
        return False
    if not re.search(r"[A-Z0-9]", article):
        return False
    if article.startswith("HTTP") or ".COM" in article:
        return False
    if re.fullmatch(r"\d{3}", article):
        return False

    return bool(re.search(r"[A-Z0-9/\-]{3,}", article)) or bool(re.search(r"\d{3,}", article))

# ✅ 오탐 가능성 높은 품번 감지
def is_suspicious_article(article: str) -> bool:
    a = article.upper()
    if re.search(r"(.)\1{2,}", a):  # 같은 문자 반복 3번 이상 (예: YGUUU003)
        return True
    if re.fullmatch(r"\d{2,3}[A-Z]{2,}X+\d{3}", a):  # 비정상 문자 반복 + X 반복
        return True
    if len(a) > 20:
        return True
    return False

# ✅ GPT 응답 파싱 (Fallback-safe JSON 파서)
def parse_gpt_response(result_text: str) -> Tuple[str, List[str], bool]:
    try:
        result = json.loads(result_text)
        company = result.get("company", "N/A").strip()
        article_numbers = result.get("article_numbers", [])
        return company, [a.strip().upper() for a in article_numbers], False
    except json.JSONDecodeError:
        # fallback 정규식 파서
        company_match = re.search(r'"?company"?\s*:\s*"([^"]+)"', result_text)
        raw_articles = re.findall(r'"([A-Z0-9/\-]{3,})"', result_text)
        company = company_match.group(1).strip() if company_match else "N/A"
        articles = list(set(raw_articles)) if raw_articles else ["N/A"]
        return company, [a.strip().upper() for a in articles], True

from collections import Counter
import re

def score_articles(gpt_articles, google_articles, tesseract_articles, crop_articles=None):
    all_sources = {
        "GPT": gpt_articles or [],
        "Google": google_articles or [],
        "Tesseract": tesseract_articles or [],
        "Crop": crop_articles or []
    }

    article_counts = Counter()
    article_sources = {}

    for source, articles in all_sources.items():
        for a in articles:
            a_clean = a.strip().upper()
            if not a_clean:
                continue
            article_counts[a_clean] += 1
            article_sources.setdefault(a_clean, set()).add(source)

    scored = []
    for article, count in article_counts.items():
        score = 0
        sources = article_sources[article]

        if "GPT" in sources:
            score += 3
        if "Google" in sources:
            score += 3
        if "Tesseract" in sources:
            score += 2
        if "Crop" in sources:
            score += 2

        if len(article) >= 6:
            score += 1
        if "-" in article or "/" in article:
            score += 1
        if re.search(r"[A-Z]{2,}", article):
            score += 1

        scored.append((article, score))

    scored.sort(key=lambda x: -x[1])
    return scored

from postprocess import is_valid_article, is_suspicious_article

def filter_scored_articles(scored_articles, company_name, max_return=5):
    normalized_company = company_name.strip().upper().replace(" ", "")
    final = []

    for article, score in scored_articles:
        article_upper = article.upper()

        if not is_valid_article(article_upper, company_name):
            continue
        if is_suspicious_article(article_upper):
            continue
        if article_upper == normalized_company:
            continue
        if normalized_company in article_upper.replace(" ", ""):
            continue
        if re.fullmatch(r"(AB[\-/]EX)?00[13]", article_upper):
            continue
        if article_upper.startswith("000"):
            continue

        final.append(article_upper)
        if len(final) >= max_return:
            break

    return final if final else ["N/A"]

from PIL import Image
import io
import pytesseract
from google.cloud import vision

# ✅ 이미지 리사이즈
def resize_image(image, max_size=(1600, 1600)):
    if image.width > max_size[0] or image.height > max_size[1]:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ Google Vision OCR
def google_vision_ocr(image: Image.Image) -> str:
    client = vision.ImageAnnotatorClient()
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    content = buffered.getvalue()
    image_google = vision.Image(content=content)
    response = client.text_detection(image=image_google)
    texts = response.text_annotations
    return texts[0].description if texts else ""

# ✅ Tesseract OCR
def tesseract_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang='eng')

# ✅ YAGI 전용 영역 OCR (Item No 위치)
def extract_yagi_article_crop(img: Image.Image) -> str:
    cropped = img.crop((480, 38, 950, 155))  # 영역은 필요 시 조정
    text = pytesseract.image_to_string(cropped, lang='eng')
    match = re.search(r'Item[#]?\s*[:\-]?\s*([A-Z0-9\-]{6,})', text.upper())
    return match.group(1) if match else "N/A"

from collections import Counter

def get_high_confidence_articles(gpt_articles, google_articles, tesseract_articles):
    all_sources = {
        "GPT": gpt_articles,
        "Google": google_articles,
        "Tesseract": tesseract_articles
    }

    article_counts = Counter()
    article_sources = {}

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
        if article.endswith("RA") or re.match(r"[A-Z]{2,}-\w+", article): score += 1
        scored.append((article, score))

    scored.sort(key=lambda x: -x[1])
    return [a for a, s in scored if s >= 6][:5]

import openai
import base64

openai.api_key = os.environ.get("OPENAI_API_KEY")

def call_gpt_ocr(image: Image.Image) -> (dict, bool):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    prompt_text = (
        "You are an OCR engine, not a reasoning AI.\n"
        "Extract exactly what is clearly visible.\n"
        "Return only:\n"
        "- company (brand name)\n"
        "- article_numbers (e.g. AB-EX123, 19023, MFA-7678)\n\n"
        "STRICT RULES:\n"
        "- Do not infer or guess.\n"
        "- If partially shown, skip.\n"
        "- If nothing visible, return 'N/A'.\n"
        "- Format: { \"company\": \"...\", \"article_numbers\": [\"...\"] }"
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
    return parse_gpt_result(result_text)

def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)

        # OCR 결과
        gpt_result, used_fallback = call_gpt_ocr(image)
        gpt_articles = gpt_result.get("article_numbers", [])
        raw_company = gpt_result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        google_articles = re.findall(r"[A-Z0-9/\-]{3,}", google_vision_ocr(image))
        tesseract_articles = re.findall(r"[A-Z0-9/\-]{3,}", tesseract_ocr(image))

        # YAGI 보정
        crop_articles = []
        if normalized_company == "YAGI":
            extracted = extract_yagi_article_crop(image)
            if extracted != "N/A":
                crop_articles = [extracted]

        # 통합 신뢰도 정제
        high_confidence = get_high_confidence_articles(
            gpt_articles + crop_articles,
            google_articles,
            tesseract_articles
        )

        # 필터링
        filtered_articles = [
            a for a in high_confidence
            if is_valid_article(a, normalized_company)
            and not is_suspicious_article(a)
            and a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

        # fallback
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

