import openai
import base64
import io
import json
import re
from PIL import Image
import os

# 🔐 OpenAI API 키 설정 (환경변수에서 불러옴)
openai.api_key = os.environ.get("OPENAI_API_KEY")

# 📦 GPT Vision 이미지 분석 함수
def extract_info_from_image(image: Image.Image) -> dict:
    try:
        # 이미지 → base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 📌 프롬프트 세팅
        prompt_text = (
            "You are an OCR assistant. Extract only the brand/company name and article number(s) from the fabric swatch image.\n"
            "- Company names often include: Co.,Ltd., TEXTILE, Inc., 株式会社\n"
            "- Article numbers may look like: BD3991, TXAB-H062, 7025-610-3, 103\n"
            "- Return strictly in JSON format like this:\n"
            "{ \"company\": \"<Brand Name>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
            "- Do not return any text outside of this JSON format.\n"
            "- If nothing found, return:\n"
            "{ \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
        )

        # 🧠 GPT Vision API 호출
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
            max_tokens=500,
        )

        result_text = response.choices[0].message.content.strip()

        # 🧪 1차 JSON 파싱
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # 🔁 fallback-safe 수동 파싱
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        # 🔍 품번 정제 필터링
        def is_valid_article(article):
            # 불용어 제거
            if article.upper() in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW"]:
                return False
            # 3자리 숫자 또는 문자 혼합 가능
            if re.match(r"(CO|NY|RA|PE)?\d{3,}", article):
                return True
            if re.match(r"[A-Z0-9\-]{3,}", article):
                return True
            return False

        result["article_numbers"] = [
            a for a in result.get("article_numbers", []) if is_valid_article(a)
        ]

        if not result.get("company"):
            result["company"] = "N/A"
        if not result.get("article_numbers"):
            result["article_numbers"] = ["N/A"]

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }


