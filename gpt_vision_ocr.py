import streamlit as st
import openai
from PIL import Image
import io
import base64
import pandas as pd
import json
import os
import concurrent.futures
import re

# 🔐 OpenAI API 키 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")

# 📦 GPT Vision 추출 함수 (fallback-safe)
def extract_info_from_image(image: Image.Image) -> dict:
    try:
        # 이미지 base64 인코딩
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        # GPT Vision 호출
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that extracts brand/company names and article numbers from fabric swatch images."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract only the **brand/company name** and **article number(s)** from the image.\n\n"
                                "- Company names often contain: Co.,Ltd., TEXTILE, Inc., 株式会社, etc.\n"
                                "- Article numbers may look like: BD3991, TXAB-H062, 7025-610-3\n\n"
                                "✅ Return **only** this JSON format:\n"
                                "{ \"company\": \"<Company>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n\n"
                                "⚠️ Do NOT include any other explanation or notes.\n"
                                "If nothing is found, return:\n"
                                "{ \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": { "url": f"data:image/png;base64,{img_b64}" }
                        }
                    ]
                }
            ],
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()
        print("🧾 GPT 응답:", result_text)

        # 1차 JSON 파싱 시도
        try:
            return json.loads(result_text)

        # 2차 fallback 파싱
        except json.JSONDecodeError:
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            article_matches = re.findall(r'"([A-Z0-9\-]{4,})"', result_text)
            return {
                "company": company_match.group(1).strip() if company_match else "[ERROR: Invalid JSON]",
                "article_numbers": list(set(article_matches)) if article_matches else ["[ERROR: Invalid JSON]"]
            }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

