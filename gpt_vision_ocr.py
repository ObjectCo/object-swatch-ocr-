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

    if re.search(r"\\bHKKH?\\b|\\bHOKKH\\b|\\bHKH\\b", name):
        return "HOKKOH"
    if "SOJITZ" in name or re.search(r"S[AE]?J[IU]?T[ZX]?", name):
        return "Sojitz Fashion Co., Ltd."
    if "LINGO" in name:
        return "Lingo"
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "UNI TEXTILE" in name:
        return "Uni Textile Co., Ltd."
    if "KOMON" in name:
        return "Komon Kobo"
    if "YAGI" in name:
        return "YAGI"

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
    if re.fullmatch(r"C\\d{2,3}%?", article):
        return False
    if re.fullmatch(r"\\d{1,2}", article):
        return False
    return re.search(r"\\d{3,}", article) is not None or re.match(r"[A-Z0-9_.\-/#]{4,}", article)

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
            "You are a vision model for extracting fabric brand name and article number.\n\n"
            "- Extract brand names like Lingo, Sojitz Fashion Co., Ltd., YAGI, Uni Textile Co., Ltd., etc.\n"
            "- Extract style numbers such as AB-EX103, KKF 2744 D/#7, WD8090, 253YGU0105, etc.\n"
            "- Style numbers can appear near 'Item#', 'Art No.', 'Product No.', or top-right box.\n"
            "- DO NOT extract phone numbers, addresses, TEL/FAX, color codes, or text like ARTICLE.\n"
            "- Return only valid codes. No duplicates.\n"
            "- If not found, return: { \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }\n"
            "- Response must be in JSON format like: { \"company\": \"BRAND\", \"article_numbers\": [\"CODE1\"] }"
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

        # JSON 파싱 시도
        try:
            result = json.loads(result_text)
            used_fallback = False
        except json.JSONDecodeError:
            used_fallback = True
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9_.\-/#]{4,})"', result_text)
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
