import zipfile

# 다시 실행 환경 초기화됨 → 파일 재생성
final_code_files = {
    "app.py": """
import streamlit as st
import openai
from PIL import Image
import io
import base64
import pandas as pd
import json
import os
import concurrent.futures
import re

# 🔐 OpenAI API 키 설정
openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ 응답 안전 파싱 함수
def safe_parse_response(result_text: str) -> dict:
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        company_match = re.search(r'"company"\\s*:\\s*"([^"]+)"', result_text)
        articles = re.findall(r'"([A-Z0-9\\-]{4,})"', result_text)
        return {
            "company": company_match.group(1).strip() if company_match else "[ERROR: Invalid JSON]",
            "article_numbers": list(set(articles)) if articles else ["[ERROR: Invalid JSON]"]
        }

# 📦 GPT Vision 이미지 분석 함수
def extract_info_from_image(image: Image.Image) -> dict:
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You're an assistant extracting company name and fabric article numbers from fabric swatch images."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please extract the brand/company name and the fabric article number(s) from this image. "
                                "Company names often include terms like 'Co.,Ltd.', 'Inc.', 'TEXTILE', '株式会社', etc. "
                                "Article numbers usually look like 'AB-EX171', 'BD3991', '7025-610-3', and so on.\\n\\n"
                                "Return in this exact JSON format:\\n"
                                "{ \\"company\\": \\"<Company Name>\\", \\"article_numbers\\": [\\"<article1>\\", \\"<article2>\\"] }\\n"
                                "If nothing is found, return 'N/A'."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300,
        )

        result_text = response.choices[0].message.content.strip()
        return safe_parse_response(result_text)

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

# 🌐 Streamlit 웹앱
st.set_page_config(page_title="Object Swatch OCR", layout="wide")
st.image("https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg", width=150)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(i_file):
        image = Image.open(i_file)
        result = extract_info_from_image(image)
        return {
            "파일명": i_file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", []))
        }

    # 🔄 병렬 처리
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(process_image, f): f.name for f in uploaded_files}
        for i, future in enumerate(concurrent.futures.as_completed(future_map)):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "파일명": future_map[future],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}"
                })
            progress.progress((i + 1) / len(uploaded_files))

    # 🧾 결과 출력
    df = pd.DataFrame(results)
    st.success("✅ 분석 완료!")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")
""",
    "requirements.txt": """
streamlit
openai
Pillow
pandas
""",
    "Dockerfile": """
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.enableCORS=false", "--server.address=0.0.0.0"]
"""
}

# zip으로 저장
output_zip_path = "/mnt/data/object_swatch_ocr_final.zip"
with zipfile.ZipFile(output_zip_path, "w") as zipf:
    for filename, content in final_code_files.items():
        file_path = f"/mnt/data/{filename}"
        with open(file_path, "w") as f:
            f.write(content.strip())
        zipf.write(file_path, arcname=filename)

output_zip_path

