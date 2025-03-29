import openai
import base64
import io
import json
import re
import os
from PIL import Image

# ✅ Cloud Run에서는 OPENAI_API_KEY 환경변수로 직접 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")


# ✅ 브랜드 정규화
def normalize_company_name(name: str) -> str:
    name = name.strip().upper()
    if re.search(r"HKKH?|HOKKH|HKH", name):
        return "HOKKOH"
    if "KOMON KOBO" in name or "小紋工房" in name:
        return "Uni Textile Co., Ltd."
    if "SOJITZ" in name:
        return "Sojitz Fashion Co., Ltd."
    if "ALLBLUE" in name:
        return "ALLBLUE Inc."
    if "MATSUBARA" in name:
        return "Matsubara Co., Ltd."
    if "YAGI" in name:
        return "YAGI"
    return name.title().replace("Co.,Ltd.", "Co., Ltd.")


# ✅ 품번 유효성 필터
def is_valid_article(article: str, company=None) -> bool:
    article = article.strip().upper()
    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if article == company:
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    return bool(re.search(r"[A-Z0-9\-/#]{3,}", article)) or bool(re.search(r"\d{3,}", article))


# ✅ 이미지 리사이즈
def resize_image(image, max_size=(1600, 1600)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image


# ✅ 메인 추출 함수
def extract_info_from_image(image: Image.Image, filename=None) -> dict:
    try:
        image = resize_image(image)
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # GPT Vision 프롬프트
        prompt_text = (
            "You are an expert OCR system for fabric swatch images.\n"
            "Extract ONLY:\n"
            "- brand name (e.g., ALLBLUE Inc., KOMON KOBO, Uni Textile Co., Ltd.)\n"
            "- article numbers (e.g., TXAB-H062, KKF 2744 D/#7, AB-EX256REA, 17200)\n\n"
            "Rules:\n"
            "- Brand name may appear anywhere (top-left, logo, footer, etc.)\n"
            "- Article numbers often appear top-middle or right.\n"
            "- DO NOT extract phone, address, composition, size, URL, color info\n"
            "- DO NOT return OCA numbers or words like TEL, HTTP\n"
            "- Return format:\n"
            "{ \"company\": \"BRAND\", \"article_numbers\": [\"CODE\"] }\n"
            "- If not found, use N/A"
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

        # ✅ JSON 파싱
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

        # 브랜드 정규화
        raw_company = result.get("company", "N/A").strip()
        normalized_company = normalize_company_name(raw_company)

        # 품번 필터링
        filtered_articles = [
            a.strip() for a in result.get("article_numbers", [])
            if is_valid_article(a, normalized_company)
        ]

        # 브랜드명 중복 제거
        filtered_articles = [
            a for a in filtered_articles
            if a.upper() != normalized_company.upper()
            and normalized_company.replace(" ", "").upper() not in a.replace(" ", "").upper()
        ]

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

