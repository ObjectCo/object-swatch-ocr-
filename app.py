import streamlit as st
import openai
import os
from PIL import Image
import io
import base64
import pandas as pd

# ✅ 환경변수에서 OpenAI 키 읽기
openai.api_key = os.environ.get("OPENAI_API_KEY")

# ✅ GPT-4o 기반 추출 함수
def extract_info_from_image(image: Image.Image):
    try:
        # 이미지 base64 인코딩
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        # OpenAI Vision API 호출
        response = openai.chat.completions.create(
            model="gpt-4o",  # ✅ 최신 모델
            messages=[
                {
                    "role": "system",
                    "content": "You're an assistant that extracts company names and fabric article numbers from fabric swatch images."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please extract the **brand/company name** and **fabric article number(s)** from this image.\n\n"
                                "- Company names include: 'Co.,Ltd.', 'Inc.', 'TEXTILE', '株式会社', etc.\n"
                                "- Article numbers look like: 'AB-EX171', 'BD3991', '7025-610-3'.\n\n"
                                "Return **only** in this JSON format:\n"
                                "{ \"company\": \"<Company Name>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n\n"
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
        result = eval(result_text)  # ✅ JSON 형태 응답이므로 안전하게 사용
        return result

    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }

# ✅ Streamlit 인터페이스
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

    # ✅ CSV 다운로드 버튼
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 결과 CSV 다운로드",
        data=csv,
        file_name="swatch_ocr_results.csv",
        mime="text/csv"
    )

