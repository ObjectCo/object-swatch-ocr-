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
    if re.search(r"\\bHKKH?\\b|\\bHOKKH\\b|\\bHKH\\b", name):
        return "HOKKOH"
    if "KOMON KOBO" in name or "\u5c0f\u7d0b\u5de5\u623f" in name:
        return "Uni Textile Co., Ltd."
    if "UNI TEXTILE" in name:
        return "Uni Textile Co., Ltd."
    if "OHARAYA" in name or "OHARA" in name:
        return "Ohara Inc."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "YAGI" in name:
        return "YAGI"
    if "VANCET" in name:
        return "Vancet"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# ✅ 품번 유효성 필터
def is_valid_article(article: str, company=None) -> bool:
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in article and re.match(r"OCA\\d{3,}", article):
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"\\d{1,2}", article):
        return False
    if re.fullmatch(r"C\\d{2,3}%?", article):
        return False
    if len(article) < 3:
        return False
    if not re.search(r"[A-Z0-9]", article):
        return False
    if article.startswith("HTTP") or ".COM" in article:
        return False
    if re.fullmatch(r"\\d{3}", article):
        return False
    return bool(re.search(r"[A-Z0-9/\\-]{3,}", article)) or bool(re.search(r"\\d{3,}", article))

# ✅ 오탐 가능성 높은 품번 감지
def is_suspicious_article(article: str) -> bool:
    a = article.upper()
    if re.search(r"(.)\\1{2,}", a):
        return True
    if re.fullmatch(r"\\d{2,3}[A-Z]{2,}X+\\d{3}", a):
        return True
    return False

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
        scored.append((article, score))

    scored.sort(key=lambda x: -x[1])
    return [a for a, s in scored if s >= 6][:5]

# ✅ 메인 추출 함수
# 🔁 최종 버전 개선 extract_info_from_image 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)

        # ✅ 우측 상단 'No.' 박스 품번 우선 추출 (ALLBLUE 전용)
        def extract_article_from_top_box(img):
            crop = img.crop((500, 20, 980, 170))
            text = pytesseract.image_to_string(crop, lang="eng")
            matches = re.findall(r"AB[-/]?EX\d{3}[A-Z]*", text.upper())
            return matches

        # 🔹 YAGI 박스 크롭
        def extract_yagi_article_crop(image):
            cropped = image.crop((520, 40, 980, 160))
            text = pytesseract.image_to_string(cropped, lang='eng')
            matches = re.findall(r"[A-Z0-9\-]{6,}", text.upper())
            return matches

        # GPT 호출
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_text = (
            "You are an OCR engine, not a reasoning AI.\n"
            "Your job is to extract only what is exactly visible in the image.\n"
            "Return only:\n"
            "1. Brand name\n2. Article numbers\n"
            "Format:\n{ \"company\": \"...\", \"article_numbers\": [\"...\"] }"
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

        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        gpt_articles = result.get("article_numbers", [])
        google_articles = re.findall(r"[A-Z0-9/\-]{3,}", google_vision_ocr(image))
        tesseract_articles = re.findall(r"[A-Z0-9/\-]{3,}", tesseract_ocr(image))

        # 크롭된 박스 OCR 우선 적용
        crop_articles = []
        if normalized_company == "ALLBLUE Inc.":
            crop_articles = extract_article_from_top_box(image)
        elif normalized_company == "YAGI":
            crop_articles = extract_yagi_article_crop(image)

        # 통합 품번 신뢰도 기반 정렬
        high_confidence = get_high_confidence_articles(
            gpt_articles + crop_articles,
            google_articles,
            tesseract_articles
        )

        filtered_articles = [
            a for a in high_confidence
            if is_valid_article(a, normalized_company)
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

        if filename and filename.lower().startswith("hk"):
            filtered_articles = [a for a in filtered_articles if a != "N/A"]

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

