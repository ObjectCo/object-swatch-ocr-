import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 브랜드 정규화 함수
def normalize_company_name(name: str, filename: str = "") -> str:
    name = name.upper()
    if re.search(r"HKK|HKH|HKKH|HOKKH", name):
        return "HOKKOH"
    if filename and filename.lower().startswith("hk"):
        return "HOKKOH"
    name = name.replace("CO.,LTD", "CO., LTD").replace("CO,LTD", "CO., LTD")
    return name.title()

# ✅ 품번 유효성 필터
def is_valid_article(article: str) -> bool:
    article = article.upper().strip()
    if article in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW"]:
        return False
    if article.startswith("OCA") and re.search(r"OCA\d{3,}", article):  # 하단 작은 텍스트 제거
        return False
    if re.match(r"^[A-Z0-9\-/# ]{3,}$", article) and re.search(r"\d{3,}", article):
        return True
    return False

# ✅ 이미지 리사이징
def resize_image(image: Image.Image, max_size=(1600, 1600)) -> Image.Image:
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ GPT Vision 추출 함수
def extract_info_from_image(image: Image.Image, filename: str = "") -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # GPT Vision 프롬프트
        prompt_text = (
            "You're an OCR assistant. Extract only the fabric swatch's brand (company name) and article number(s).\n"
            "- Company names may include: Co.,Ltd., TEXTILE, Inc., 株式会社, etc.\n"
            "- Article numbers usually look like: BD3991, TXAB-H062, KYC 424-W D/#3, 103, etc.\n"
            "- Prefer article numbers that are large and located near the top or center of the image.\n"
            "- DO NOT extract small bottom text like 'OCA4-5239' or phone numbers.\n"
            "- Format must be JSON ONLY like:\n"
            "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
            "- Do NOT include any explanation or text outside JSON.\n"
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
            max_tokens=700,
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱 or fallback
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(articles)) if articles else ["N/A"]
            }

        # 브랜드 정제
        result["company"] = normalize_company_name(result.get("company", "N/A"), filename)

        # 품번 정제
        cleaned_articles = []
        for a in result.get("article_numbers", []):
            if is_valid_article(a):
                cleaned_articles.append(a.strip())
        result["article_numbers"] = cleaned_articles or ["N/A"]

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

