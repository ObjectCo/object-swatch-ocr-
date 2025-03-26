import os
import io
import re
from PIL import Image
import google.generativeai as genai

# ✅ model 객체 전역으로 선언되도록 try 밖으로 이동
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-pro-vision")  # ✅ 안전하게 밖에서 선언

def extract_company_and_article(image: Image.Image) -> dict:
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()

    prompt = (
        "You're analyzing a fabric swatch information sheet. "
        "Please extract the **company name** and the **article number(s)**. \n"
        "- Company names often end with 'Co.,Ltd.', 'Inc.', '工房', '株式会社', or contain words like 'TEXTILE'.\n"
        "- Article numbers look like codes such as 'AB-EX171', 'WD8090', 'BD3991', '7025-610-3'.\n\n"
        "🎯 Return your answer in the following JSON format only:\n"
        "{\n"
        "  \"company\": \"<Company Name>\",\n"
        "  \"article_numbers\": [\"<article1>\", \"<article2>\"]\n"
        "}\n\n"
        "If either field is not found, return 'N/A'."
    )

    try:
        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": image_bytes}
        ])

        text = response.text.strip()
        print("🧪 Gemini 응답 원문:", text)

        company_match = re.search(r'"company"\s*:\s*"([^"]+)"', text)
        articles_match = re.findall(r'"([A-Z]{1,5}-?[A-Z]{0,5}\d{3,6}(?:-\d{1,3})?)"', text)

        result = {
            "company": company_match.group(1).strip() if company_match else "N/A",
            "article_numbers": list(set(articles_match)) if articles_match else ["N/A"]
        }

        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }
