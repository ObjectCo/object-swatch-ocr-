import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

def normalize_company_name(name, filename=None):
    name = name.upper()
    if re.search(r"HKKH|HKK|HKH|HOKKH", name):
        return "HOKKOH"
    if filename and filename.lower().startswith("hk"):
        return "HOKKOH"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.").replace("Matsubara.Co.,Ltd", "Matsubara Co., Ltd.")

def is_valid_article(article):
    article = article.upper()
    if article in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):  # OCA 제거
        return False
    if re.search(r"\d{3,}", article):  # 숫자 3자리 이상
        return True
    if re.match(r"[A-Z0-9\-/#]{3,}", article):
        return True
    return False

def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_text = (
            "You're an OCR assistant. Extract only the fabric swatch's **brand (company name)** and **article number(s)**.\n"
            "- Company names may include: Co.,Ltd., TEXTILE, Inc., 株式会社, HOKKOH, etc.\n"
            "- Article numbers examples: BD3991, TXAB-H062, KYC 424-W D/#3, 103\n"
            "- Return JSON only:\n"
            "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
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

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        result["company"] = normalize_company_name(result.get("company", ""), filename)

        result["article_numbers"] = [
            a.strip() for a in result.get("article_numbers", []) if is_valid_article(a)
        ]

        if filename and filename.lower().startswith("hk"):
            if result["company"] == "N/A":
                result["company"] = "HOKKOH"
            result["article_numbers"] = [a for a in result["article_numbers"] if a != "N/A"]
            if not result["article_numbers"]:
                result["article_numbers"] = []

        if not result["article_numbers"]:
            result["article_numbers"] = ["N/A"]

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }


