import os
import io
from PIL import Image
import google.generativeai as genai

def extract_text(image: Image.Image) -> str:
    # 환경 변수에서 API 키 가져오기
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    
    # Gemini 설정
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-pro-vision")

    # 이미지 → 바이트 변환
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()

    # 🧠 여기서 핵심: Article Number만 추출하도록 명확한 지시어 작성
    prompt = (
        "You are analyzing a fabric swatch image. "
        "Please extract only the article number or product number, such as 'BD3991', 'AB-EX171', 'WD8090', '7025-610-3'. "
        "Do not include general words like 'COTTON', 'WASHABLE', 'JAPAN', or other unrelated text. "
        "Return only the article number(s), separated by commas if multiple. "
        "If none found, return 'N/A'."
    )

    try:
        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": image_bytes}
        ])
        result = response.text.strip()
        print("🧪 Gemini 추출 결과:", result)  # 디버깅용 출력
        return result
    except Exception as e:
        return f"[ERROR] {str(e)}"
