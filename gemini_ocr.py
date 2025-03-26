import io
import re
from PIL import Image
import vertexai
from vertexai.vision_models import ImageToTextModel, Image as GeminiImage

# ✅ Cloud 프로젝트 설정
# Cloud Run 또는 로컬 실행 시 환경변수 또는 vertexai.init()에서 자동 감지 가능
vertexai.init(project="your-project-id", location="us-central1")  # 🔁 반드시 us-central1

def extract_company_and_article(image_pil: Image.Image) -> dict:
    try:
        # 이미지 → 바이트 변환
        img_byte_arr = io.BytesIO()
        image_pil.save(img_byte_arr, format="PNG")
        image_bytes = img_byte_arr.getvalue()

        # Vertex AI용 이미지 객체 생성
        gemini_image = GeminiImage(image_bytes=image_bytes)
        model = ImageToTextModel.from_pretrained("gemini-1.0-pro-vision")

        # 🧠 프롬프트: 회사명 + 아티클 넘버 JSON 형식으로 요청
        prompt = (
            "Please analyze this fabric swatch image and extract the company name and article number(s).\n"
            "- Article numbers look like: AB-EX171, BD3991, 1025-600-3, etc.\n"
            "- Company names usually include: 'Co.,Ltd.', 'Inc.', 'Textile', '株式会社', etc.\n\n"
            "🎯 Return only this JSON format:\n"
            "{\n"
            "  \"company\": \"<Company Name>\",\n"
            "  \"article_numbers\": [\"<article1>\", \"<article2>\"]\n"
            "}"
        )

        response = model.predict(image=gemini_image, prompt=prompt, max_output_tokens=1024)
        text = response.text.strip()
        print("🧪 Gemini 응답 원문:", text)

        # 정규식으로 JSON-like 응답 파싱
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
