import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import os
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image  # 외부 모듈로 분리된 분석 함수

# 페이지 설정
st.set_page_config(page_title="Object Swatch OCR", layout="wide")
st.image("https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg", width=150)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader(
    "이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True
)

# 결과 표시
if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    thumbnails = []
    progress = st.progress(0)

    def process_image(uploaded_file):
        image = Image.open(uploaded_file)
        result = extract_info_from_image(image)

        # 썸네일 생성 (base64로 변환)
        buffered = io.BytesIO()
        image.thumbnail((150, 150))
        image.save(buffered, format="PNG")
        encoded_image = base64.b64encode(buffered.getvalue()).decode()
        img_html = f'<img src="data:image/png;base64,{encoded_image}" width="100"/>'

        return {
            "파일명": uploaded_file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", [])),
            "썸네일": img_html,
            "원본": uploaded_file
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {
            executor.submit(process_image, f): f.name for f in uploaded_files
        }
        for i, future in enumerate(concurrent.futures.as_completed(future_map)):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                results.append({
                    "파일명": future_map[future],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}",
                    "썸네일": "❌",
                    "원본": None
                })
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")

    # 테이블 구성
    for r in results:
        col1, col2, col3 = st.columns([1.5, 3, 1])
        with col1:
            st.markdown(r["썸네일"], unsafe_allow_html=True)
        with col2:
            st.markdown(f"**📁 {r['파일명']}**")
            st.markdown(f"**🏷 브랜드명:** {r['브랜드명']}")
            st.markdown(f"**🔢 품번:** {r['품번']}")
        with col3:
            if r["원본"]:
                with st.expander("🔍 원본 이미지 보기", expanded=False):
                    st.image(r["원본"], use_column_width=True)

    # CSV 다운로드
    df = pd.DataFrame([
        {
            "파일명": r["파일명"],
            "브랜드명": r["브랜드명"],
            "품번": r["품번"]
        } for r in results
    ])
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 결과 CSV 다운로드",
        data=csv,
        file_name="swatch_ocr_results.csv",
        mime="text/csv"
    )

