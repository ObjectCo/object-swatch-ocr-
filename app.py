import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
from gemini_ocr import extract_text_from_image
from extract_article import extract_article_numbers

st.set_page_config(page_title="Object Swatch OCR", layout="wide")

st.image("object_logo.jpg", width=180)
st.title("📦 Object Swatch OCR")
st.write("이미지를 업로드하면 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", accept_multiple_files=True, type=["png", "jpg", "jpeg"])

results = []

for uploaded_file in uploaded_files:
    image = Image.open(uploaded_file)
    
    with st.spinner(f"🔍 품번 추출 중: {uploaded_file.name}"):
        try:
            raw_text = extract_text_from_image(image)
            articles = extract_article_numbers(raw_text)
            result = ", ".join(articles) if articles else "N/A"
        except Exception as e:
            result = f"❌ 오류: {str(e)}"
    
    results.append({
        "File Name": uploaded_file.name,
        "Thumbnail": image,
        "Extracted Articles": result
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
            st.write(result["Extracted Articles"])

    df = pd.DataFrame([{
        "File Name": r["File Name"],
        "Extracted Articles": r["Extracted Articles"]
    } for r in results])

    csv = df.to_csv(index=False).encode("utf-8")
    b64 = base64.b64encode(csv).decode()
    st.markdown(
        f'<a href="data:file/csv;base64,{b64}" download="extracted_articles.csv">📥 결과 CSV 다운로드</a>',
        unsafe_allow_html=True
    )
