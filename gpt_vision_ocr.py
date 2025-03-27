import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    if "YAGI" in name:
        return "YAGI"
    if re.search(r"\\bHKKH?\\b|\\bHOKKH\\b|\\bHKH\\b", name):
        return "HOKKOH"
    if re.search(r"S[AE]?J[IU]?T[ZX]?", name):
        return "Sojitz Fashion Co., Ltd."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "LINGO" in name:
        return "Lingo"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

def is_valid_article(article, company=None):
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE"]:
        return False
    if "OCA" in article and re.match(r"OCA\\d{3,}", article):
        return False
    if company and article.upper() == company.upper():
        return False
    if re.fullmatch(r"\\d{1,2}", article):
        return False
    return re.search(r"[A-Z0-9\\-/#]{3,}", article) is not None

def resize_image(image: Image.Image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_text = (
            "You are an expert OCR model for extracting fabric swatch info.\n"
            "- Extract the exact 'brand name' (e.g., YAGI, ALLBLUE Inc., HOKKOH).\n"
            "- ONLY extract the article number from the top-right label box under 'No.' or 'Article'.\n"
            "- Ignore TEL/FAX, phone numbers, composition, color, website URLs, and anything not in top-right label.\n"
            "- Return JSON in this format:\n"
            "{ \"company\": \"BRAND\", \"article_numbers\": [\"CODE1\"] }\n"
            "- If no valid info, return: { \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
        )

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

        try:
            result = json.loads(result_text)
            used_fallback = False
        except json.JSONDecodeError:
            used_fallback = True
            company_match = re.search(r'"company"\\s*:\\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'AB-EX\\d{3,}(?:REA)?', result_text) or \
                           re.findall(r'[A-Z0-9]{2,}-[A-Z0-9/#]{2,}', result_text)
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

        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "") not in a.replace(" ", "")
            and "/" not in a and a.upper() != "N/A"
        ]

        if filename and filename.lower().startswith("hk"):
            if normalized_company == "N/A":
                normalized_company = "HOKKOH"

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

