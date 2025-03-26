iimport streamlit as st
import openai
from PIL import Image
import io
import base64
import pandas as pd
import json
import os

# ✅ OpenAI API Key 환경변수에서 불러오기
openai.api_key = os.environ.get("OPENAI_API_KEY")


def extract_info_from_image(image: Image.Image):
    try:
        # 이미지 → base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You're an assistant extracting company name and article numbers from fabric swatch images."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please extract the brand/company name and the fabric article number(s) from this image. "
                                "Company names include 'Co.,Ltd.', 'Inc.', 'TEXTILE', '株式会社', etc. "
                                "Article numbers look like 'AB-EX171', 'BD3991', '7025-610-3'.\n\n"
                                "Return in this exact JSON format:\n"
                                "{ \"company\": \"<Company Name>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
                                "If not found, return 'N/A'."
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
        
        # 💥 여기서 문제가 생기고 있었음!
        try:
            result = json.loads(result_text)  # 안전한 파싱
        except json.JSONDecodeError:
            # GPT 응답이 JSON 형식이 아닐 때 대비
            return {
                "company": "[ERROR]",
                "article_numbers": [f"[ERROR] Invalid JSON: {result_text}"]
            }

        return {
            "company": result.get("company", "N/A"),
            "article_numbers": result.get("article_numbers", ["N/A"])
        }

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

# Streamlit 웹앱 UI
st.set_page_config(page_title="Object Swatch OCR", layout="wide")
st.image("https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg", width=150)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    results = []
    progress = st.progress(0)
    for i, uploaded_file in enumerate(uploaded_files):
        image = Image.open(uploaded_file)
        result = extract_info_from_image(image)
        results.append({
            "파일명": uploaded_file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", []))
        })
        progress.progress((i + 1) / len(uploaded_files))

    df = pd.DataFrame(results)
    st.success("✅ 모든 이미지 분석 완료!")
    st.dataframe(df, use_container_width=True)

    # CSV 다운로드
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 결과 CSV 다운로드",
        data=csv,
        file_name="swatch_ocr_results.csv",
        mime="text/csv"
    )
