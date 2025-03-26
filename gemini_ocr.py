import os
import io
import json
import re
import requests
from PIL import Image
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# 프로젝트 설정
PROJECT_ID = "your-project-id"  # ✅ 실제 GCP 프로젝트 ID로 변경
REGION = "us-central1"
MODEL_ID = "gemini-1.0-pro-vision"

# 서비스 계정 키로 인증 토큰 생성
def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    return credentials.token

# 메인 추출 함수
def extract_company_and_article(image_pil: Image.Image) -> dict:
    try:
        # 이미지 → base64 인코딩
        img_byte_arr = io.BytesIO()
        image_pil.save(img_byte_arr, format='PNG')
        image_bytes = img_byte_arr.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # 프롬프트 구성
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

        # 요청 준비
        endpoint = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{MODEL_ID}:predict"
        access_token = get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        body = {
            "instances": [
                {
                    "prompt": prompt,
                    "image": {
                        "bytesBase64Encoded": image_base64,
                        "mimeType": "image/png"
                    }
                }
            ],
            "parameters": {
                "temperature": 0.4,
                "maxOutputTokens": 1024,
                "topP": 1,
                "topK": 40
            }
        }

        response = requests.post(endpoint, headers=headers, json=body)
        result = response.json()
        text = result["predictions"][0]["content"]

        print("🧪 Gemini 응답:", text)

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
