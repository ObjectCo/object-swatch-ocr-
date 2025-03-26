import base64
import google.generativeai as genai
from PIL import Image
import io
import os

# 환경 변수에서 API 키 가져오기
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-pro-vision")

def extract_text(image: Image.Image) -> str:
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()

    try:
        response = model.generate_content([
            "Please extract all text from this fabric swatch image.",
            {
                "mime_type": "image/png",
                "data": image_bytes
            }
        ])
        return response.text.strip()
    except Exception as e:
        return f"[ERROR] {str(e)}"
