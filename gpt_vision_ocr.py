import openai
import base64
import io
import json
import re
import os
from PIL import Image
import pytesseract
from google.cloud import vision

openai.api_key = os.environ.get("OPENAI_API_KEY")


# ✅ 브랜드명 정규화
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"\bHKKH?\b|\bHOKKH\b|\bHKH\b", name):
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
    return bool(re.search(r"[A-Z0-9/\-]{3,}", article)) or bool(re.search(r"\d{3,}", article))


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


# ✅ 주요 OCR 통합 처리 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # ✅ GPT Vision 프롬프트
        prompt_text = (
            "You are an OCR expert for fabric swatch cards.\n\n"
            "Your job is to extract exactly and only the following:\n"
            "1. The brand name (e.g., KOMON KOBO, Uni Textile Co., Ltd., ALLBLUE Inc.)\n"
            "2. Article numbers (e.g., AB-EX003REA, KKP2338, KCL600, etc.)\n\n"
            "⚠️ VERY IMPORTANT:\n"
            "- DO NOT guess or autocorrect. Extract exactly what appears in the image.\n"
            "- DO NOT substitute or fix possible typos. Use raw OCR text as-is.\n"
            "- If the text is unclear, skip it. Do not invent or assume values.\n\n"
            "Rules:\n"
            "- Brand name may appear in logo area, header, or footer.\n"
            "- Article numbers may appear top-right, center, or lower-right.\n"
            "- Ignore phone numbers, addresses, URLs, 'OCA' codes, color, size, composition.\n"
            "- Format MUST be JSON:\n"
            "  { \"company\": \"...\", \"article_numbers\": [\"...\"] }\n"
            "- If no data found, use \"N/A\"\n"
        )

        # ✅ GPT 호출
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

        # ✅ JSON 파싱
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

        # ✅ OCR 보조 추출 (Google & Tesseract)
        google_text = google_vision_ocr(image)
        tesseract_text = tesseract_ocr(image)

        combined_text = "\n".join([google_text, tesseract_text])
        ocr_articles = re.findall(r"[A-Z0-9/\-]{3,}", combined_text)

        # ✅ GPT + OCR 통합 품번 후보
        gpt_articles = result.get("article_numbers", [])
        all_candidates = list(set(gpt_articles + ocr_articles))

        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        # ✅ 유효 품번 필터링
        filtered_articles = [
            a.strip() for a in all_candidates
            if is_valid_article(a, normalized_company)
        ]

        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

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


