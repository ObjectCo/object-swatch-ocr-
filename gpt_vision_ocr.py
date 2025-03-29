import openai
import base64
import io
import json
import re
import os
from PIL import Image

# ✅ OpenAI API Key는 환경 변수에서 불러옴
openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 브랜드명 정규화 함수
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"\bHKKH?\b|\bHOKKH\b|\bHKH\b", name):
        return "HOKKOH"
    if "KOMON KOBO" in name or "小紋工房" in name:
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

    # 제외 조건
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    if len(article) < 3:
        return False
    if not re.search(r"[A-Z0-9]", article):
        return False
    if article.startswith("HTTP") or ".COM" in article:
        return False

    # 유효 패턴: 알파벳+숫자 조합, 하이픈 또는 슬래시 포함, 3자 이상 숫자
    return bool(re.search(r"[A-Z0-9\-/]{3,}", article)) or bool(re.search(r"\d{3,}", article))

# ✅ 이미지 리사이즈 (추론 속도 및 처리 최적화)
def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

# ✅ Vision 기반 브랜드 및 품번 추출 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        # 이미지 전처리
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 🔎 GPT 프롬프트 구성
        prompt_text = (
            "You are a professional OCR system specialized in fabric swatch images.\n\n"
            "Your job is to extract ONLY the following information from the image:\n"
            "1. The brand name (e.g., ALLBLUE Inc., KOMON KOBO, Uni Textile Co., Ltd., etc.)\n"
            "2. Article numbers (e.g., AB-EX256REA, BD3991, KYC 424-W D/#3, TXAB-H062, 17200, etc.)\n\n"
            "📌 Strict rules:\n"
            "- Brand name can appear anywhere: logo area, top-left, footer, etc.\n"
            "- Article numbers appear usually top-right, near 'No.' or '品番' or 'Article'\n"
            "- DO NOT extract composition, color info, size, weight, phone, address, URL\n"
            "- DO NOT include anything starting with TEL, FAX, HTTP, WWW\n"
            "- DO NOT include 'OCAxxxx' numbers or generic keywords like 'Cotton', 'Denim'\n"
            "- Return format (in pure JSON):\n"
            "{ \"company\": \"BRAND NAME\", \"article_numbers\": [\"ARTICLE1\", \"ARTICLE2\"] }\n"
            "- Use 'N/A' if not found.\n"
            "- NEVER return ranges like 'KYC424 to 426' — instead return each separately.\n"
            "- Be precise and concise.\n"
        )

        # GPT Vision API 호출
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

        # ✅ JSON 파싱 시도
        try:
            result = json.loads(result_text)
            used_fallback = False
        except json.JSONDecodeError:
            # Fallback-safe 파싱
            used_fallback = True
            company_match = re.search(r'"?company"?\s*:\s*"([^"]+)"', result_text)
            raw_articles = re.findall(r'"([A-Z0-9\-/]{3,})"', result_text)
            result = {
                "company": company_match.group(1).strip() if company_match else "N/A",
                "article_numbers": list(set(raw_articles)) if raw_articles else ["N/A"]
            }

        # ✅ 브랜드 정규화
        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        # ✅ 품번 필터링
        filtered_articles = [
            a.strip() for a in result.get("article_numbers", [])
            if is_valid_article(a, normalized_company)
        ]

        # ✅ 중복 제거 (브랜드명이 품번으로 인식된 경우)
        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

        # ✅ 'hk' 파일명의 경우 N/A 제거 (원단명 추정 가능)
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
