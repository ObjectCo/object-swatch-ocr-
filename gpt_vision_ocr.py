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

# ✅ OpenAI API 키 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 브랜드명 정규화
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()

    normalization_map = {
        r"\bHKKH?\b|\bHOKKH\b|\bHKH\b": "HOKKOH",
        "KOMON KOBO": "Uni Textile Co., Ltd.",
        "UNI TEXTILE": "Uni Textile Co., Ltd.",
        "OHARAYA": "Ohara Inc.",
        "OHARA": "Ohara Inc.",
        "ALLBLUE": "ALLBLUE Inc.",
        "MATSUBARA": "Matsubara Co., Ltd.",
        "YAGI": "YAGI",
        "VANCET": "Vancet",
        "COSMO": "COSMO TEXTILE CO., LTD.",
        "JAPAN BLUE": "Japan Blue Co., Ltd.",
    }

    for pattern, normalized in normalization_map.items():
        if re.search(pattern, name):
            return normalized

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
    return True

# ✅ 오탐 가능성 높은 품번 감지
def is_suspicious_article(article: str) -> bool:
    a = article.upper()
    if re.search(r"(.)\1{2,}", a):  # 같은 문자 반복 3번 이상
        return True
    if re.fullmatch(r"\d{2,3}[A-Z]{2,}X+\d{3}", a):  # 비정상 문자 반복
        return True
    return False

# ✅ 이미지 리사이즈
def resize_image(image, max_size=(1600, 1600)):
    if image.width > max_size[0] or image.height > max_size[1]:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ GPT Vision OCR
def gpt_ocr(image: Image.Image) -> dict:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    prompt = (
        "You are an OCR engine. Extract visible data only.\n"
        "Return only brand name and article numbers like:\n"
        "{ \"company\": \"...\", \"article_numbers\": [\"...\"] }"
    )

    try:
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

        content = response.choices[0].message.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # fallback 수동 추출
            company_match = re.search(r'"?company"?\s*:\s*"([^"]+)"', content)
            raw_articles = re.findall(r'"([A-Z0-9/\-]{3,})"', content)
            return {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

    except Exception as e:
        return {"company": "[ERROR]", "article_numbers": [f"[ERROR] {str(e)}"]}

# ✅ Google Vision OCR
def google_vision_ocr(image: Image.Image) -> str:
    client = vision.ImageAnnotatorClient()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_data = vision.Image(content=buf.getvalue())
    response = client.text_detection(image=image_data)
    return response.text_annotations[0].description if response.text_annotations else ""

# ✅ Tesseract OCR
def tesseract_ocr(image: Image.Image) -> str:
    return pytesseract.image_to_string(image, lang='eng')

# ✅ 신뢰도 기반 품번 정렬
def get_high_confidence_articles(gpt_articles, google_articles, tesseract_articles, normalized_company):
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
            if not is_valid_article(a_clean, normalized_company):
                continue
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

# ✅ 최종 추출 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)

        # 🔹 GPT
        gpt_result = gpt_ocr(image)
        raw_company = gpt_result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)
        gpt_articles = [a.strip().upper() for a in gpt_result.get("article_numbers", [])]

        # 🔹 Google / Tesseract
        google_text = google_vision_ocr(image)
        tesseract_text = tesseract_ocr(image)

        google_articles = re.findall(r"[A-Z0-9/\-]{3,}", google_text.upper())
        tesseract_articles = re.findall(r"[A-Z0-9/\-]{3,}", tesseract_text.upper())

        # 🔹 통합 스코어링 기반 추출
        high_confidence = get_high_confidence_articles(
            gpt_articles, google_articles, tesseract_articles, normalized_company
        )

        filtered_articles = [
            a for a in high_confidence
            if not is_suspicious_article(a)
            and a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

        # 🔹 fallback
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
            "used_fallback": not bool(filtered_articles)
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"],
            "used_fallback": True
        }
