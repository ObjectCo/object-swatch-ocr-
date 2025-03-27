# ✅ GPT Vision 기반 원단 스와치 OCR 개선 버전
# 정확도 98%를 목표로 한 정제된 로직

import openai
import base64
import io
from PIL import Image
import os
import json
import re

openai.api_key = os.environ.get("OPENAI_API_KEY")

def encode_image(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def normalize_brand(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"HKK|HKH|HKKH|HOKKH", name):
        return "HOKKOH"
    if "SOJITZ" in name:
        return "Sojitz Fashion Co., Ltd."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "KOMON" in name:
        return "KOMON KOBO"
    if "YAGI" in name:
        return "YAGI"
    return name.title()

def is_valid_article(article: str) -> bool:
    article = article.upper()
    if any(keyword in article for keyword in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "OCA"]):
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    return bool(re.search(r"\d{3,}", article)) or bool(re.match(r"[A-Z0-9\-/#]{4,}", article))

def extract_info_from_image(image: Image.Image) -> dict:
    try:
        # Step 1: Get raw OCR text from image
        img_b64 = encode_image(image)
        vision_prompt = """
        You are an OCR system. Extract all visible text from this fabric swatch image. 
        Include brand names, article numbers, labels, and ignore visual noise.
        """

        vision_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": vision_prompt.strip()},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]}
            ],
            max_tokens=1500
        )

        raw_text = vision_response.choices[0].message.content.strip()

        # Step 2: Analyze that text to extract brand + article number
        analyze_prompt = f"""
        Below is raw OCR text from a fabric label:

        {raw_text}

        Extract:
        1. Brand name (e.g. HOKKOH, ALLBLUE Inc., Sojitz Fashion Co., Ltd.)
        2. Valid article numbers (e.g. BD3991, TXAB-H062, 253YGU0105, 2916)

        Ignore TEL, FAX, OCA, Article, HTTP, WWW, Color, Composition, and any unrelated info.

        Return strict JSON like:
        {{ "company": "BRAND", "article_numbers": ["CODE1", "CODE2"] }}
        If nothing is found, return:
        {{ "company": "N/A", "article_numbers": ["N/A"] }}
        """

        analyze_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": analyze_prompt.strip()}
            ],
            max_tokens=700
        )

        result_text = analyze_response.choices[0].message.content.strip()

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # fallback: extract with regex
            company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
            article_matches = re.findall(r'"([A-Z0-9\-/#]{3,})"', result_text)
            result = {
                "company": company_match.group(1) if company_match else "N/A",
                "article_numbers": list(set(article_matches)) if article_matches else ["N/A"]
            }

        # Final cleanup
        company = normalize_brand(result.get("company", "N/A"))
        article_numbers = [a for a in result.get("article_numbers", []) if is_valid_article(a)]

        if not article_numbers:
            article_numbers = ["N/A"]

        return {
            "company": company,
            "article_numbers": article_numbers
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }
