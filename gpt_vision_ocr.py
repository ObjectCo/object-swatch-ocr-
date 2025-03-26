import os
import io
import base64
from PIL import Image
import requests

def extract_company_and_article(image: Image.Image) -> dict:
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"company": "[ERROR]", "article_numbers": ["[ERROR] OPENAI_API_KEY not set"]}

        # 이미지 → base64 인코딩
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        image_bytes = img_byte_arr.getvalue()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # OpenAI GPT-4 Vision API 호출
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "You're analyzing a fabric swatch image.\n"
                                "Please extract:\n"
                                "1. The **brand or company name** (usually in large font, e.g. 'KOMON KOBO', 'ALLBLUE Inc.', 'MATSUBARA Co.,Ltd.')\n"
                                "2. The **article number(s)** (usually alphanumeric codes like 'AB-EX171', 'BD3991', '7025-610-3')\n\n"
                                "Return JSON like this:\n"
                                "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n\n"
                                "Ignore irrelevant text like phone numbers, addresses, keywords like 'COTTON', 'POLYESTER', etc."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        text = result["choices"][0]["message"]["content"]

        # 결과 파싱
        import re
        company_match = re.search(r'"company"\s*:\s*"([^"]+)"', text)
        article_matches = re.findall(r'"([A-Z]{1,5}-?[A-Z]{0,5}\d{3,6}(?:-\d{1,3})?)"', text)

        return {
            "company": company_match.group(1).strip() if company_match else "N/A",
            "article_numbers": list(set(article_matches)) if article_matches else ["N/A"]
        }

    except Exception as e:
        return {"company": "[ERROR]", "article_numbers": [f"[ERROR] {str(e)}"]}

