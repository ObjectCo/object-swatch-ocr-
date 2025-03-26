import io
import re
import base64
from typing import Dict
from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account

# ✅ Cloud Run에 마운트된 서비스 계정 키 경로
CREDENTIAL_PATH = "/secrets/GOOGLE_APPLICATION_CREDENTIALS"

# ✅ Vision API 클라이언트 생성
credentials = service_account.Credentials.from_service_account_file(CREDENTIAL_PATH)
client = vision.ImageAnnotatorClient(credentials=credentials)

# ✅ 브랜드명, 품번 추출 함수
def extract_company_and_article(image: Image.Image) -> Dict:
    try:
        # 이미지 → 바이트 변환
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        content = img_byte_arr.getvalue()

        # Vision API 요청
        image_for_api = vision.Image(content=content)
        response = client.text_detection(image=image_for_api)

        texts = response.text_annotations
        if not texts:
            return {"company": "N/A", "article_numbers": ["N/A"]}

        raw_text = texts[0].description
        print("🧾 OCR 전체 텍스트:", raw_text)

        # 브랜드명 추출
        company_pattern = re.compile(r"\b(?:[A-Z][A-Za-z&.,\s\-]{2,}TEXTILE|[A-Z][A-Za-z&.,\s\-]+(?:Co\.?,? Ltd\.?|Inc\.?|株式会社|工房))\b", re.IGNORECASE)
        company_match = company_pattern.findall(raw_text)
        company_name = company_match[0].strip() if company_match else "N/A"

        # 아티클 번호 추출
        article_pattern = re.compile(r"\b(?:[A-Z]{1,5}-)?[A-Z]{1,5}[-]?\d{3,6}(?:[-]\d{1,3})?\b|\b\d{4,6}\b")
        all_matches = article_pattern.findall(raw_text)

        # 잡 텍스트 필터링
        EXCLUDE_KEYWORDS = {
            "JAPAN", "TOKYO", "OSAKA", "WASHABLE", "COTTON", "LINEN", "LABEL", "WARM", "COOL",
            "WATER", "DESIGN", "COLOR", "SIZE", "COMPO", "STRETCH", "EFFECT", "RESISTANT",
            "QUALITY", "VINTAGE", "TEXTILE", "MADE", "BANSHU-ORI", "TEL", "FAX", "INC", "LTD",
            "CO", "NO", "ARTICLE", "HTTPS", "WWW", "URL", "ATTENTION", "PLEASE", "WE", "ARE",
            "THE", "AND", "IN", "OF", "WITH", "FOR", "ON", "BY"
        }

        articles = []
        for token in all_matches:
            token_clean = token.strip().upper()
            if token_clean in EXCLUDE_KEYWORDS:
                continue
            if re.match(r"\d{2,4}-\d{2,4}-\d{2,4}", token_clean):
                continue
            if re.fullmatch(r"\d{4}", token_clean) and not re.search(r"[A-Z]", token_clean):
                continue
            articles.append(token_clean)

        return {
            "company": company_name,
            "article_numbers": list(set(articles)) if articles else ["N/A"]
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

