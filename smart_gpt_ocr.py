# smart_gpt_ocr.py

import openai
import base64
import io
from PIL import Image
import os
import json

openai.api_key = os.environ.get("OPENAI_API_KEY")

def extract_raw_text_from_image(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    prompt_text = "Please extract all readable text from this fabric swatch image."

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]}
        ],
        max_tokens=1500
    )

    return response.choices[0].message.content.strip()

def extract_company_and_articles_from_text(text: str) -> dict:
    prompt = f"""
Below is raw text from a fabric swatch image:

{text}

From this, extract only:
- Brand name (e.g., YAGI, HOKKOH, ALLBLUE Inc.)
- Valid article numbers (3+ digit codes like TXAB-H062, 2916)

Ignore TEL, FAX, Article, Color, Address, etc.

Return JSON:
{{ "company": "BRAND", "article_numbers": ["CODE1", "CODE2"] }}
If nothing found, return:
{{ "company": "N/A", "article_numbers": ["N/A"] }}
"""

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=700
    )

    try:
        return json.loads(response.choices[0].message.content.strip())
    except:
        return { "company": "N/A", "article_numbers": ["N/A"] }

def extract_info_from_image(image: Image.Image):
    raw_text = extract_raw_text_from_image(image)
    result = extract_company_and_articles_from_text(raw_text)
    return result
