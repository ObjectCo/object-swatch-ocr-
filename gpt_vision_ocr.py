import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

# 브랜드명 정규화 함수
def normalize_company_name(name):
    name = name.upper()
    if re.search(r"HKK|HKH|HKKH|HOKKH", name):
        return "HOKKOH"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

def extract_info_from_image(image: Image.Image) -> dict:
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_text = (
            "You're an OCR assistant. Extract only the fabric swatch's brand (company name) and article number(s).\n"
            "- Company names may include: Co.,Ltd., TEXTILE, Inc., 株式会社, etc.\n"
            "- Article numbers usually look like: BD3991, TXAB-H062, KYC 424-W D/#3, 103, etc.\n"
            "- If multiple articles exist, return them all in a list.\n"
            "- Format must be JSON ONLY like:\n"
            "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
            "- Do NOT include explanations or any other text.\n"
            "- If not found, return:\n"
            "{ \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
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
            max_tokens=600,
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱 시도
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # fallback 파싱
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        # 추가 정제 로직
        def is_valid_article(article):
            if article.upper() in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW"]:
                return False
            if re.search(r"\d{3,}", article):  # 숫자 3자리 이상 포함
                return True
            if re.match(r"[A-Z0-9\-/#]{3,}", article):
                return True
            return False

        result["article_numbers"] = [
            a.strip() for a in result.get("article_numbers", []) if is_valid_article(a)
        ]
        if not result["article_numbers"]:
            result["article_numbers"] = ["N/A"]

        if result.get("company"):
            result["company"] = normalize_company_name(result["company"])
        else:
            result["company"] = "N/A"

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

