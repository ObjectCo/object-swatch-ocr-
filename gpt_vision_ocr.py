import openai
import base64
import io
import json
import re
from PIL import Image
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

def extract_info_from_image(image: Image.Image) -> dict:
    try:
        # 이미지 인코딩
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_text = (
            "You are an OCR assistant. Extract only the brand/company name and article number(s) from the fabric swatch image.\n"
            "- Company names include: Co.,Ltd., TEXTILE, Inc., 株式会社\n"
            "- Article numbers look like: BD3991, TXAB-H062, 7025-610-3, 103\n"
            "- Do NOT return ranges like '4001-4003'. Return each article number explicitly.\n"
            "- Return only valid article numbers, each at least 3 characters, alphanumeric.\n"
            "- Output strictly JSON only. No explanation, no markdown, no text around.\n"
            "- Format:\n"
            "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
            "- If not found, return:\n"
            "{ \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
        )

        # GPT Vision 호출
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

        # 1차: JSON 파싱
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # 2차: 수동 파싱 fallback
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        # ✅ 후처리: 품번 필터링
        def is_valid_article(a):
            if a.upper() in ["ARTICLE", "TEL", "FAX", "HTTP", "WWW", "URL"]:
                return False
            if "-" in a and re.fullmatch(r"[A-Z]*\d{3,}-\d{3,}", a):  # 의심 범위표현 제거
                return False
            return re.fullmatch(r"[A-Z0-9\-]{3,}", a) is not None

        result["article_numbers"] = [a for a in result.get("article_numbers", []) if is_valid_article(a)]

        # ✅ 후처리: 브랜드명 보정
        brand_corrections = {
            "Cosmo": "COSMO TEXTILE CO., LTD.",
            "Cosmo Co., Ltd.": "COSMO TEXTILE CO., LTD.",
            "Oharayaseni Co.,Ltd": "Oharayaseni Co.,Ltd.",
        }
        brand = result.get("company", "N/A")
        result["company"] = brand_corrections.get(brand, brand)

        # ✅ 기본값 보정
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

