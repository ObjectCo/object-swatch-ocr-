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
    return name.title().replace("Co.,Ltd.", "Co., Ltd.").replace("Co.,ltd.", "Co., Ltd.")

# 품번 유효성 검사
def is_valid_article(article):
    article = article.upper()
    if article in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW"]:
        return False
    if re.search(r"\d{3,}", article):  # 숫자 3자리 이상 포함
        return True
    if re.match(r"[A-Z0-9\-/#]{3,}", article):
        return True
    return False

def extract_info_from_image(image: Image.Image) -> dict:
    try:
        # ✅ 리사이징: 1600px 이하로 축소 (속도 향상)
        max_width = 1600
        if image.width > max_width:
            ratio = max_width / float(image.width)
            new_height = int((float(image.height) * float(ratio)))
            image = image.resize((max_width, new_height))

        # 이미지 → base64 인코딩
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
            max_tokens=700,
        )

        result_text = response.choices[0].message.content.strip()

        # 1차: JSON 응답 시도
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # fallback: 정규표현식 수동 추출
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        # 품번 필터링 및 브랜드 정규화
        result["article_numbers"] = [
            a.strip() for a in result.get("article_numbers", []) if is_valid_article(a)
        ] or ["N/A"]

        result["company"] = normalize_company_name(result.get("company", "N/A"))

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

