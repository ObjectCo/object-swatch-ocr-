import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

# 브랜드 정규화 함수
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"HKK|HKH|HKKH|HOKKH", name):
        return "HOKKOH"
    if re.search(r"S[AE]?J[IU]?T[ZX]?", name):
        return "Sojitz Fashion Co., Ltd."
    if "LINGO" in name:
        return "Lingo"
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# 품번 유효성 필터
def is_valid_article(article, company=None):
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE"]:
        return False
    if re.search(r"OCA\d{3,}", article):  # OCA 시리즈 제거
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    if article in ["80143", "HS2291"]:  # 알려진 잘못된 오탐 번호 제거
        return False
    return re.search(r"\d{3,}", article) or re.match(r"[A-Z]{2,10}[-/]?\d{3,}", article)

# 이미지 리사이징
def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# 메인 추출 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 간결하고 핵심 중심 프롬프트
        prompt = """
You're a fabric swatch analyzer.
Extract the brand name (company) and article number(s) from the image.

Guidelines:
- Brand names include words like Co., Ltd., Inc., Textile, Fashion, etc.
- Article numbers often appear after: ART NO., PRODUCT NO., ITEM NO., or inside angle brackets (e.g., <WD8909>)
- Return clean JSON like:
{ "company": "BRAND NAME", "article_numbers": ["CODE1", "CODE2"] }

If not found:
{ "company": "N/A", "article_numbers": ["N/A"] }
        """.strip()

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

        # JSON 파싱
        try:
            result = json.loads(result_text)
            used_fallback = False
        except json.JSONDecodeError:
            used_fallback = True
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        filtered_articles = [
            a.strip() for a in result.get("article_numbers", [])
            if is_valid_article(a, normalized_company)
        ]

        # 브랜드명이 품번으로 포함된 경우 제거
        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "") not in a.replace(" ", "")
        ]

        # hk 파일 예외 처리
        if filename and filename.lower().startswith("hk"):
            normalized_company = "HOKKOH"
            filtered_articles = [a for a in filtered_articles if a.upper() != "N/A"]
            if not filtered_articles:
                filtered_articles = ["N/A"]

        return {
            "company": normalized_company or "N/A",
            "article_numbers": filtered_articles or ["N/A"],
            "used_fallback": used_fallback
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"],
            "used_fallback": True
        }
