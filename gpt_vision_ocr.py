import openai
import base64
import io
import json
import re
from PIL import Image
import os
from difflib import get_close_matches

openai.api_key = os.environ.get("OPENAI_API_KEY")

# ---------------------
# 브랜드 정규화 함수
# ---------------------
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()

    if re.search(r"\bHKKH?\b|\bHOKKH\b|\bHKH\b", name):
        return "HOKKOH"
    if re.search(r"S[AE]?J[IU]?T[ZX]?", name):
        return "Sojitz Fashion Co., Ltd."
    if "LINGO" in name:
        return "Lingo"
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "ALLBLUE" in name:
        return "Allblue Inc."
    if "YAGI" in name:
        return "YAGI"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# ---------------------
# 품번 유효성 필터
# ---------------------
def is_valid_article(article, company=None):
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if article == company:
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    return re.search(r"\d{3,}", article) is not None or re.match(r"[A-Z0-9\-/#]{3,}", article)

# ---------------------
# 흐릿한 숫자 보정: 유사 숫자 대체
# ---------------------
def correct_similar_articles(articles):
    corrected = []
    known_patterns = [
        "253YGU0104", "253YGU0106", "253YGU0206", "253YGU0306", "253YGU0308",
        "253YGU0000", "253YGU0094", "253YGU0098", "253YGU0103"
    ]
    for art in articles:
        best_match = get_close_matches(art.upper(), known_patterns, n=1, cutoff=0.8)
        corrected.append(best_match[0] if best_match else art)
    return list(set(corrected))

# ---------------------
# 이미지 리사이징
# ---------------------
def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ---------------------
# 메인 추출 함수
# ---------------------
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt_text = (
            "You are a vision model for extracting fabric brand name and article number.\n\n"
            "- Extract brand names like Lingo, Sojitz Fashion Co., Ltd., Matsubara, ALLBLUE Inc., YAGI etc.\n"
            "- Extract article numbers like WD8090, LIG4020-RE, BD3991, TXAB-H062, 253YGU0104 etc.\n"
            "- Ignore phone numbers, addresses, TEL/FAX, colors, and unrelated text.\n"
            "- Prioritize article numbers from top-right area.\n"
            "- Return strictly in JSON format: { \"company\": \"BRAND\", \"article_numbers\": [\"CODE1\"] }\n"
            "- If not found, return { \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
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
            raw_articles = re.findall(r'"([A-Z0-9\-/# ]{3,})"', result_text)
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

        # 브랜드명이 품번에 포함된 경우 제거
        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and (normalized_company.replace(" ", "") not in a.replace(" ", ""))
        ]

        # 흐릿한 품번 보정
        filtered_articles = correct_similar_articles(filtered_articles)

        # HOKKOH 케이스 강제 처리
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

