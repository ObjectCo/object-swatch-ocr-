import streamlit as st
import openai
from PIL import Image
import io
import base64
import pandas as pd
import json
import os
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image

st.set_page_config(page_title="Object Swatch OCR", layout="wide")
st.image("https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg", width=150, use_column_width="auto")
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def resize_image(image: Image.Image, max_size: int = 1000) -> Image.Image:
        width, height = image.size
        if max(width, height) <= max_size:
            return image
        ratio = max_size / max(width, height)
        return image.resize((int(width * ratio), int(height * ratio)))

    def process_image(i_file):
        image = Image.open(i_file).convert("RGB")
        image = resize_image(image)

        result = extract_info_from_image(image)
        return {
            "파일명": i_file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", [])),
            "이미지": image
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(process_image, f): f.name for f in uploaded_files}
        for i, future in enumerate(concurrent.futures.as_completed(future_map)):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "파일명": future_map[future],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}",
                    "이미지": None
                })
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")

    # 결과 표시
    for res in results:
        col1, col2 = st.columns([1, 5])
        with col1:
            if res["이미지"]:
                st.image(res["이미지"], caption=res["파일명"], width=100)
                with st.expander("🔍 원본 이미지 보기"):
                    st.image(res["이미지"], use_column_width=True)
        with col2:
            st.write(f"📄 **{res['파일명']}**")
            st.write(f"🏷️ **브랜드명:** {res['브랜드명']}")
            st.write(f"🧵 **품번:** {res['품번']}")

    # CSV 다운로드
    df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "이미지"} for r in results
    ])
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")

