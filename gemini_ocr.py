import os
import io
import re
from PIL import Image
import google.generativeai as genai

def extract_text(image: Image.Image) -> list[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("models/gemini-pro-vision")

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()

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
        result_text = response.text.strip()
        print("🧪 Gemini 원문 응답:", result_text)

        # ✅ 정규식으로 품번만 추출
        pattern = re.compile(r'\b(?:[A-Z]{1,5}-)?[A-Z]{1,5}[-]?\d{3,6}(?:[-]\d{1,3})?\b|\b\d{4,6}\b')
        matches = pattern.findall(result_text)
        return list(set(matches)) if matches else ["N/A"]
    except Exception as e:
        return [f"[ERROR] {str(e)}"]
