# 최신 최적화된 gpt_vision_ocr.py 버전 생성
from pathlib import Path

code = '''
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

    # HOKKOH 오탐 패턴
    if re.search(r"\\bHKKH?\\b|\\bHOKKH\\b|\\bHKH\\b", name):
        return "HOKKOH"

    # Sojitz 오탐 패턴
    if re.search(r"S[AE]?J[IU]?T[ZX]?", name):  # Septex, Sajtex, Sujin, Sojitz, Sajta 등
        return "Sojitz Fashion Co., Ltd."

    # Lingo
    if "LINGO" in name:
        return "Lingo"

    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# 품번 유효성 필터
def is_valid_article(article, company=None):
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE"]:
        return False
    if "OCA" in article and re.match(r"OCA\\d{3,}", article):
        return False
    if article == company:
        return False
    if re.fullmatch(r"C\\d{2,3}%?", article):  # C100% 같은 성분 정보 제거
        return False
    if re.fullmatch(r"\\d{1,2}", article):  # 1~2자리 숫자 제거
        return False
    return re.search(r"\\d{3,}", article) is not None or re.match(r"[A-Z0-9\\-/#]{3,}", article)

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
            "You're a fabric OCR extraction model. Extract only the 'Brand name (company)' and 'Article number(s)'.\\n\\n"
            "- The brand name (company) can include keywords like Co.,Ltd., Co., Ltd., Inc., TEXTILE, Fashion, Company, etc.\\n"
            "- The article numbers usually appear near the top, in formats like: BD3991, TXAB-H062, KYC 424-W D/#3, 2916, LIG4020-RE, etc.\\n"
            "- DO NOT include anything that looks like phone numbers, addresses, TEL, FAX, URLs, or color names.\\n"
            "- DO NOT extract any number or text from bottom-left or bottom-right of the image unless clearly a product code.\\n"
            "- DO NOT return ranges or multi-line values (like 'OSDC40031~33'), instead return each code individually.\\n"
            "- Remove all duplicates or invalid entries.\\n"
            "- Common OCR mistakes to fix: Sojitz may appear as Sujin, Septex, Sajtex, Sajta, etc. Normalize to 'Sojitz Fashion Co., Ltd.'.\\n"
            "- Also normalize HKK, HKH, HKKH to HOKKOH.\\n"
            "- Prioritize article numbers that appear in top-right of the image.\\n\\n"
            "Return ONLY in JSON format like below:\\n"
            "{ \\"company\\": \\"BRAND NAME\\", \\"article_numbers\\": [\\"CODE1\\", \\"CODE2\\"] }\\n\\n"
            "If not found, return:\\n"
            "{ \\"company\\": \\"N/A\\", \\"article_numbers\\": [\\"N/A\\"] }\\n"
            "No other text or explanation."
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
            used_fallback = False
        except json.JSONDecodeError:
            used_fallback = True
            company_match = re.search(r'"company"\\s*:\\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\\-/ #]{3,})"', result_text)
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
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and (normalized_company.replace(" ", "") not in a.replace(" ", ""))
        ]

        # 특수 케이스: hk 파일은 브랜드명 강제 HOKKOH
        if filename and filename.lower().startswith("hk"):
            normalized_company = "HOKKOH"
            filtered_articles = [a for a in filtered_articles if a.upper() != "N/A"]
            if not filtered_articles:
                filtered_articles = ["N/A"]

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
