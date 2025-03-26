import os
import io
import json  # ✅ 이 줄 추가!
import base64
import re
import requests
from PIL import Image

def extract_company_and_article(image: Image.Image) -> dict:
    # Load environment variable
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return {"company": "[ERROR]", "article_numbers": ["[ERROR] GOOGLE_APPLICATION_CREDENTIALS not set"]}

    # Load service account key
    try:
        with open(creds_path, "r") as f:
            service_account_info = json.load(f)
            access_token = get_access_token(service_account_info)
    except Exception as e:
        return {"company": "[ERROR]", "article_numbers": [f"[ERROR] Failed to read credentials: {str(e)}"]}

    # Prepare image
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Prepare prompt
    prompt = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "You're analyzing a fabric swatch information sheet. "
                            "Please extract the **company name** and the **article number(s)**.\n"
                            "- Company names often end with 'Co.,Ltd.', 'Inc.', '工房', '株式会社', or contain 'TEXTILE'.\n"
                            "- Article numbers look like 'AB-EX171', 'BD3991', '7025-610-3'.\n\n"
                            "🎯 Return your answer in this exact JSON format:\n"
                            "{ \"company\": \"<Company Name>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n\n"
                            "If not found, return 'N/A'."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_b64
                        }
                    }
                ]
            }
        ]
    }

    # Call Gemini API
    endpoint = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-vision-pro:generateContent"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        response = requests.post(endpoint, headers=headers, json=prompt)
        response.raise_for_status()
        result_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]

        company_match = re.search(r'"company"\s*:\s*"([^"]+)"', result_text)
        articles_match = re.findall(r'"([A-Z]{1,5}-?[A-Z]{0,5}\d{3,6}(?:-\d{1,3})?)"', result_text)

        return {
            "company": company_match.group(1).strip() if company_match else "N/A",
            "article_numbers": list(set(articles_match)) if articles_match else ["N/A"]
        }

    except Exception as e:
        return {"company": "[ERROR]", "article_numbers": [f"[ERROR] {str(e)}"]}

def get_access_token(service_account_info):
    import google.auth
    import google.auth.transport.requests
    import google.oauth2.service_account

    credentials = google.oauth2.service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token
