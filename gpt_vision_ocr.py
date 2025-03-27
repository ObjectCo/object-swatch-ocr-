import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

# 브랜드 정규화
def normalize_company_name(name):
    name = name.upper()
    if re.search(r"HKK|HKH|HKKH|HOKKH", name):
        return "HOKKOH"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# 품번 필터링
def is_valid_article(article):
    article = article.upper()
    if article in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW"]:
        return False
    if "OCA" in article and re.search(r"OCA[- ]?\d{3,}", article):  # 하단 OCA 코드 제거
        return False
    if re.search(r"\d{3,}", article):  # 숫자 3자리 이상 포함
        return True
    if re.match(r"[A-Z0-9\-/#]{3,}", article):
        return True
    return False

# 리사이징
def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# OCR 추출 함수
def extract_info_from_image(image: Image.Image) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = (
            "You are an OCR assistant. Extract ONLY the brand name (company) and article number(s) of the fabric swatch.\n"
            "- Brand names may include: Co.,Ltd., Inc., TEXTILE, 株式会社, etc.\n"
            "- Article numbers look like: BD3991, TXAB-H062, KYC 424-W D/#3, etc.\n"
            "- Do not extract unrelated codes like TEL, OCA, FAX, ARTICLE, etc.\n"
            "- Only return the main article number that appears in the top section of the image.\n"
            "- Format:\n"
            "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
            "- If not found, return:\n"
            "{ \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
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
            max_tokens=600,
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

        # 필터링
        result["article_numbers"] = [
            a.strip() for a in result.get("article_numbers", []) if is_valid_article(a)
        ]
        if not result["article_numbers"]:
            result["article_numbers"] = ["N/A"]

        result["company"] = normalize_company_name(result.get("company", ""))

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

