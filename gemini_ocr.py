import io
import re
import os
import base64
from PIL import Image
from google.cloud import vision

# ✅ GCP 인증 키 환경변수 확인
cred_path = "/secrets/GOOGLE_APPLICATION_CREDENTIALS"
if not os.path.exists(cred_path):
    raise EnvironmentError("❌ GOOGLE_APPLICATION_CREDENTIALS 파일이 존재하지 않습니다.")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

client = vision.ImageAnnotatorClient()

# 추출 필터링 키워드
EXCLUDE_KEYWORDS = {
    "JAPAN", "TOKYO", "OSAKA", "WASHABLE", "COTTON", "LINEN", "LABEL", "WARM", "COOL",
    "WATER", "DESIGN", "COLOR", "SIZE", "COMPO", "STRETCH", "EFFECT", "RESISTANT",
    "QUALITY", "VINTAGE", "TEXTILE", "MADE", "BANSHU-ORI", "TEL", "FAX", "INC", "LTD",
    "CO", "NO", "ARTICLE", "HTTPS", "WWW", "URL", "ATTENTION", "PLEASE", "WE", "ARE",
    "THE", "AND", "IN", "OF", "WITH", "FOR", "ON", "BY", "g/m²", "100%", "C-", "PE"
}

# 브랜드 후보군
KNOWN_BRANDS = [
    "KOMON KOBO", "ALLBLUE Inc.", "MATSUBARA CO.,LTD.", "COSMO TEXTILE", "AGUNINO",
    "HKK", "HK TEXTILE", "UNI TEXTILE", "JAPAN BLUE", "CHAMBRAY", "SHIBAYA"
]

def extract_company_and_article(image: Image.Image) -> dict:
    try:
        # 이미지 -> 바이너리 변환
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        content = img_byte_arr.getvalue()

        # Vision API 요청
        image_obj = vision.Image(content=content)
        response = client.text_detection(image=image_obj)
        texts = response.text_annotations

        if not texts:
            return {"company": "N/A", "article_numbers": ["N/A"]}

        ocr_text = texts[0].description.upper()

        # 🔍 브랜드명 추출
        found_brand = "N/A"
        for brand in KNOWN_BRANDS:
            if brand.upper() in ocr_text:
                found_brand = brand
                break

        # 🔍 품번 정규식 추출
        raw_matches = re.findall(r"\b[A-Z]{0,4}-?[A-Z]{0,4}\d{3,6}(?:-\d{1,3})?\b", ocr_text)
        filtered_articles = []
        for item in raw_matches:
            cleaned = item.strip().upper()
            if cleaned in EXCLUDE_KEYWORDS:
                continue
            if re.match(r"^\d{4}$", cleaned):  # 너무 단순한 숫자 제거 (예: 2023)
                continue
            filtered_articles.append(cleaned)

        result = {
            "company": found_brand,
            "article_numbers": list(set(filtered_articles)) if filtered_articles else ["N/A"]
        }
        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

