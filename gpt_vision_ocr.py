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
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# 품번 유효성 필터
def is_valid_article(article, company=None):
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if article == company:
        return False
    if re.fullmatch(r"\d{1,4}", article):  # 단순 숫자만 있는 경우 제외
        return False
    return re.search(r"\d{3,}", article) is not None or re.match(r"[A-Z0-9\-/#]{3,}", article)

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

        prompt_text = (
            "You're an OCR assistant. Extract only the fabric swatch's brand (company name) and article number(s).\n"
            "- Company names may include: Co.,Ltd., TEXTILE, Inc., 株式会社, etc.\n"
            "- Article numbers look like: BD3991, TXAB-H062, KYC 424-W D/#3, 103, etc.\n"
            "- Multiple articles should be returned in a list.\n"
            "- Format: { \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
            "- If nothing is found: { \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }\n"
            "- NO explanation or other content."
        )

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                { "role": "system", "content": "You are a helpful assistant." },
                {
                    "role": "user",
                    "content": [
                        { "type": "text", "text": prompt_text },
                        { "type": "image_url", "image_url": { "url": f"data:image/png;base64,{img_b64}" } }
                    ]
                }
            ],
            max_tokens=700,
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        # 품번 필터링 및 정제
        filtered_articles = [
            a.strip() for a in result.get("article_numbers", [])
            if is_valid_article(a, normalized_company)
        ]

        # 브랜드명이 품번으로 포함될 경우 제거
        filtered_articles = [
            a for a in filtered_articles if a.upper() != normalized_company.upper()
        ]

        # 특수 케이스: hk 파일은 브랜드명 강제 HOKKOH
        if filename and filename.lower().startswith("hk"):
            normalized_company = "HOKKOH"
            # N/A 제거
            filtered_articles = [a for a in filtered_articles if a.upper() != "N/A"]
            if not filtered_articles:
                filtered_articles = ["N/A"]

        return {
            "company": normalized_company if normalized_company else "N/A",
            "article_numbers": filtered_articles if filtered_articles else ["N/A"]
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

