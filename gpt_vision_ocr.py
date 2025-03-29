import openai
import base64
import io
import json
import re
import os
from PIL import Image

# ✅ OpenAI API Key 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 브랜드명 정규화

def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"\\bHKKH?\\b|\\bHOKKH\\b|\\bHKH\\b", name):
        return "HOKKOH"
    if "KOMON KOBO" in name or "\u5c0f\u7d0b\u5de5\u623f" in name:
        return "Uni Textile Co., Ltd."
    if "UNI TEXTILE" in name:
        return "Uni Textile Co., Ltd."
    if "OHARAYA" in name or "OHARA" in name:
        return "Ohara Inc."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "YAGI" in name:
        return "YAGI"
    if "VANCET" in name:
        return "Vancet"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")

# ✅ 품번 유효성 필터
def is_valid_article(article: str, company=None) -> bool:
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in article and re.match(r"OCA\\d{3,}", article):
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"\\d{1,2}", article):
        return False
    if re.fullmatch(r"C\\d{2,3}%?", article):
        return False
    if len(article) < 3:
        return False
    if not re.search(r"[A-Z0-9]", article):
        return False
    if article.startswith("HTTP") or ".COM" in article:
        return False
    return bool(re.search(r"[A-Z0-9\\-/]{3,}", article)) or bool(re.search(r"\\d{3,}", article))

# ✅ 이미지 리사이즈
def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ GPT Vision 기반 품번/브랜드 추출 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # ✅ 강화된 GPT 프롬프트
        prompt_text = (
            "You are an OCR expert for fabric swatch cards.\n\n"
            "Your job is to extract only the following from the image:\n"
            "1. The brand name (e.g., KOMON KOBO, Uni Textile Co., Ltd., ALLBLUE Inc.)\n"
            "2. Article numbers (e.g., AB-EX003REA, KKP2338, KKF 8825CD, KCL600, etc.)\n\n"
            "Rules:\n"
            "- Brand name may appear in logo area (top-left), header, or footer.\n"
            "- If you see '小紋工房', interpret it as KOMON KOBO (Uni Textile Co., Ltd.)\n"
            "- Article numbers may appear top-right, center or lower-right, often near '品番', 'No.', or 'Article'.\n"
            "- DO NOT extract phone, address, website, composition, color, size, URL, or 'OCA' codes.\n"
            "- Ignore anything with TEL, FAX, HTTP, WWW, or non-descriptive numbers.\n"
            "- Avoid ranges like '424~426'. List each article number separately.\n"
            "- Format MUST be pure JSON:\n"
            "  { \"company\": \"...\", \"article_numbers\": [\"...\"] }\n"
            "- Use 'N/A' if nothing is found.\n"
        )

        # ✅ API 호출
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

        # ✅ JSON 파싱 or fallback
        try:
            result = json.loads(result_text)
            used_fallback = False
        except json.JSONDecodeError:
            used_fallback = True
            company_match = re.search(r'"?company"?\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9/\-]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        # ✅ 필터링 및 후처리
        filtered_articles = [
            a.strip() for a in result.get("article_numbers", [])
            if is_valid_article(a, normalized_company)
        ]

        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

        # ✅ 'hk' 파일 특수 처리
        if filename and filename.lower().startswith("hk"):
            filtered_articles = [a for a in filtered_articles if a != "N/A"]

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
