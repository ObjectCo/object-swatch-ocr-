# 🔥 최종 완전체 초고도화 OCR 추출기
# GPT-4o + Google Vision + Tesseract + 전처리 + 고정 위치 OCR + 품번 정규화 + 신뢰도 기반 필터링

import openai
import base64
import io
import json
import re
import os
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from google.cloud import vision
from collections import Counter

openai.api_key = os.environ.get("OPENAI_API_KEY")

def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    patterns = {
        r"\bHKKH?\b|\bHOKKH\b|\bHKH\b": "HOKKOH",
        r"KOMON KOBO|小紋工房|UNI TEXTILE": "Uni Textile Co., Ltd.",
        r"OHARAYA|OHARA": "Ohara Inc.",
        r"ALLBLUE": "ALLBLUE Inc.",
        r"MATSUBARA": "Matsubara Co., Ltd.",
        r"YAGI": "YAGI",
        r"VANCET": "Vancet",
    }
    for pat, repl in patterns.items():
        if re.search(pat, name):
            return repl
    return name.title()

def is_valid_article(article: str, company=None) -> bool:
    a = article.strip().upper()
    if a in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in a and re.match(r"OCA\d{3,}", a): return False
    if company and a == company.upper(): return False
    if len(a) < 3 or re.fullmatch(r"\d{1,2}", a): return False
    if re.fullmatch(r"C\d{2,3}%?", a): return False
    if article.startswith("HTTP") or ".COM" in article: return False
    if re.fullmatch(r"\d{3}", a): return False
    return bool(re.search(r"[A-Z0-9/\-]{3,}", a)) or bool(re.search(r"\d{3,}", a))

def preprocess_image(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    sharp = gray.filter(ImageFilter.SHARPEN)
    enhanced = ImageEnhance.Contrast(sharp).enhance(2.0)
    return enhanced

def google_vision_ocr(image: Image.Image) -> str:
    client = vision.ImageAnnotatorClient()
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    content = buffered.getvalue()
    image_google = vision.Image(content=content)
    response = client.text_detection(image=image_google)
    texts = response.text_annotations
    return texts[0].description if texts else ""

def tesseract_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang='eng')

def call_gpt_ocr(image: Image.Image) -> dict:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    prompt = (
        "You are an OCR engine. Extract:\n"
        "1. Brand name (company)\n2. Article numbers (model codes)\n\n"
        "Strict rules:\n"
        "- No assumptions or inference\n- Return only what's visible\n"
        "- JSON format only:\n{ \"company\": \"...\", \"article_numbers\": [\"...\"] }"
    )
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]
            }
        ],
        max_tokens=700,
    )
    result_text = response.choices[0].message.content.strip()
    try:
        result = json.loads(result_text)
        used_fallback = False
    except json.JSONDecodeError:
        used_fallback = True
        company_match = re.search(r'"?company"?\s*:\s*"([^"]+)"', result_text)
        raw_articles = re.findall(r'"([A-Z0-9/\-]{3,})"', result_text)
        result = {
            "company": company_match.group(1).strip() if company_match else "N/A",
            "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
        }
    return result, used_fallback

def extract_fixed_region_ocr(image: Image.Image, box=(520, 40, 980, 160)) -> list:
    cropped = image.crop(box)
    text = pytesseract.image_to_string(cropped, lang='eng')
    return re.findall(r"[A-Z0-9\-]{5,}", text.upper())

def rank_article_numbers(articles: list) -> list:
    counts = Counter(articles)
    scored = []
    for a, cnt in counts.items():
        score = cnt
        if len(a) >= 6: score += 1
        if "-" in a or "/" in a: score += 1
        scored.append((a, score))
    return [a for a, s in sorted(scored, key=lambda x: -x[1]) if s >= 3]

def extract_info_from_image_ultra(image: Image.Image, filename=None) -> dict:
    try:
        image = preprocess_image(image)

        gpt_result, used_fallback = call_gpt_ocr(image)
        raw_company = gpt_result.get("company", "N/A")
        gpt_articles = gpt_result.get("article_numbers", [])
        company = normalize_company_name(raw_company)

        google_articles = re.findall(r"[A-Z0-9/\-]{3,}", google_vision_ocr(image))
        tesseract_articles = re.findall(r"[A-Z0-9/\-]{3,}", tesseract_ocr(image))
        fixed_articles = extract_fixed_region_ocr(image) if company == "YAGI" else []

        all_articles = gpt_articles + google_articles + tesseract_articles + fixed_articles
        filtered = [
            a for a in all_articles
            if is_valid_article(a, company)
            and a.upper() != company.upper()
            and company.replace(" ", "").upper() not in a.replace(" ", "")
        ]

        final_articles = rank_article_numbers(filtered)
        return {
            "company": company,
            "article_numbers": final_articles[:3] if final_articles else ["N/A"],
            "used_fallback": used_fallback
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"],
            "used_fallback": True
        }


