import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
from gemini_ocr import extract_company_and_article  # ✅ 함수 직접 불러옴

st.set_page_config(page_title="Object Swatch OCR", layout="wide")

st.image("object_logo.jpg", width=180)
st.title("📦 Object Swatch OCR")
st.write("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

results = []

for uploaded_file in uploaded_files:
    image = Image.open(uploaded_file)

    with st.spinner(f"🔍 Gemini Vision으로 분석 중: {uploaded_file.name}"):
        try:
            result = extract_company_and_article(image)
            company = result.get("company", "N/A")
            articles = result.get("article_numbers", ["N/A"])
            extracted_text = ", ".join(articles)
        except Exception as e:
            company = "[ERROR]"
            extracted_text = f"[ERROR] {str(e)}"

    results.append({
        "File Name": uploaded_file.name,
        "Company": company,
        "Extracted Articles": extracted_text,
        "Thumbnail": image
    })

if results:
    st.markdown("---")
    st.subheader("📋 추출 결과")

    for result in results:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image(result["Thumbnail"], width=100)
        with col2:
            st.markdown(f"**{result['File Name']}**")
            st.write(f"🏢 **브랜드명**: {result['Company']}")
            st.write(f"📦 **품번**: {result['Extracted Articles']}")

    # CSV 다운로드
    df = pd.DataFrame([{
        "File Name": r["File Name"],
        "Company": r["Company"],
        "Extracted Articles": r["Extracted Articles"]
    } for r in results])

    csv = df.to_csv(index=False).encode("utf-8")
    b64 = base64.b64encode(csv).decode()
    st.markdown(
        f'<a href="data:file/csv;base64,{b64}" download="extracted_articles.csv">📥 결과 CSV 다운로드</a>',
        unsafe_allow_html=True
    )

