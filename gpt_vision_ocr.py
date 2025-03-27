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
    if re.search(r"\bHKKH?\b|\bHOKKH\b|\bHKH\b", name):
        return "HOKKOH"
    if re.search(r"S[AE]?J[IU]?T[ZX]?", name):
        return "Sojitz Fashion Co., Ltd."
    if "LINGO" in name:
        return "Lingo"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

def is_valid_article(article, company=None):
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):  # 성분
        return False
    if re.fullmatch(r"\d{1,2}", article):  # 너무 짧은 숫자
        return False
    if company and article == company:
        return False
    # 핵심 조건: 영문/숫자/기호 조합 4자 이상
    return re.match(r"[A-Z0-9\-/#]{4,}", article) is not None

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
            "You're a fabric OCR extraction model. Extract ONLY:\n"
            "1. Brand name (e.g. Sojitz Fashion Co., Ltd., Lingo, HOKKOH)\n"
            "2. Article number(s) (e.g. BD3991, LIG4020-RE, 2916)\n\n"
            "Avoid:\n"
            "- Phone numbers, FAX, URLs, addresses\n"
            "- Colors or composition (C100%, Ny 100%)\n"
            "- Ranges like 40031~33 (list them separately)\n\n"
            "Return JSON only:\n"
            "{ \"company\": \"BRAND\", \"article_numbers\": [\"CODE1\"] }\n"
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

        # Fallback-safe 파싱
        try:
            result = json.loads(result_text)
            used_fallback = False
        except json.JSONDecodeError:
            used_fallback = True
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/ #]{4,})"', result_text)
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
            and (normalized_company.replace(" ", "") not in a.replace(" ", ""))
        ]

        # 특수: hk 파일은 브랜드 고정
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

