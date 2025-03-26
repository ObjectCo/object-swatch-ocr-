import io
import re
from PIL import Image
import vertexai
from vertexai.vision_models import ImageToTextModel, Image as GeminiImage

# ✅ Cloud 프로젝트 및 리전 설정
vertexai.init(project="your-project-id", location="us-central1")

# ✅ 메인 함수: app.py에서 임포트할 함수
def extract_company_and_article(image_pil: Image.Image) -> dict:
    try:
        # 이미지 → byte 변환
        img_byte_arr = io.BytesIO()
        image_pil.save(img_byte_arr, format="PNG")
        image_bytes = img_byte_arr.getvalue()

        # Gemini Vision 모델 준비
        gemini_image = GeminiImage(image_bytes=image_bytes)
        model = ImageToTextModel.from_pretrained("gemini-1.0-pro-vision")

        # 프롬프트: 회사명 + 품번을 JSON 형태로 추출 요청
        prompt = (
            "You're analyzing a fabric swatch. Please extract the company name and article number(s). "
            "Article numbers look like: AB-EX171, BD3991, 1025-600-3, etc. "
            "Company names often contain 'TEXTILE', 'Co.,Ltd.', 'Inc.', '株式会社', etc.\n\n"
            "🎯 Respond only in this JSON format:\n"
            "{\n"
            "  \"company\": \"<Company Name>\",\n"
            "  \"article_numbers\": [\"<article1>\", \"<article2>\"]\n"
            "}"
        )

        # 추론 요청
        response = model.predict(image=gemini_image, prompt=prompt, max_output_tokens=1024)
        text = response.text.strip()

        # JSON-like 응답 파싱
        company_match = re.search(r'"company"\s*:\s*"([^"]+)"', text)
        articles_match = re.findall(r'"([A-Z]{1,5}-?[A-Z]{0,5}\d{3,6}(?:-\d{1,3})?)"', text)

        return {
            "company": company_match.group(1).strip() if company_match else "N/A",
            "article_numbers": list(set(articles_match)) if articles_match else ["N/A"]
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }
