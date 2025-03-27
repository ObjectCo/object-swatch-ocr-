import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import os
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image

st.set_page_config(page_title="Object Swatch OCR", layout="wide", page_icon="📦")

# ✅ 로고 출력
st.markdown(
    "<img src='https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg' style='height: 60px;'>",
    unsafe_allow_html=True,
)

st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No.)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(file):
        image = Image.open(file).convert("RGB")

        # ✅ 최적화를 위한 리사이징 (너무 클 경우)
        max_size = (1600, 1600)
        image.thumbnail(max_size)

        # 썸네일 이미지 생성
        thumbnail = image.copy()
        thumbnail.thumbnail((300, 300))
        buffered = io.BytesIO()
        thumbnail.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 🔍 OCR 실행
        result = extract_info_from_image(image, filename=file.name)

        return {
            "파일명": file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", [])),
            "img_b64": img_b64
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
                    "img_b64": ""
                })
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")
    st.markdown("아래 결과 테이블을 **엑셀에 복사**하여 사용하세요.")

    # ✅ HTML 테이블 구성
    table_html = """
    <style>
    .ocr-table {
        border-collapse: collapse;
        width: 100%;
        font-size: 15px;
        color: white;
    }
    .ocr-table th, .ocr-table td {
        border: 1px solid #444;
        padding: 8px;
        text-align: left;
        vertical-align: middle;
    }
    .ocr-table th {
        background-color: #333;
    }
    .img-thumb {
        height: 60px;
        cursor: pointer;
        transition: transform 0.2s ease;
    }
    .img-thumb:hover {
        transform: scale(2.2);
        z-index: 999;
    }
    </style>
    <table class='ocr-table'>
        <thead>
            <tr>
                <th>썸네일</th>
                <th>파일명</th>
                <th>브랜드명</th>
                <th>품번</th>
            </tr>
        </thead>
        <tbody>
    """

    for r in results:
        image_tag = (
            f"<img class='img-thumb' src='data:image/png;base64,{r['img_b64']}'>" if r["img_b64"] else "N/A"
        )
        table_html += f"""
        <tr>
            <td>{image_tag}</td>
            <td>{r['파일명']}</td>
            <td>{r['브랜드명']}</td>
            <td>{r['품번']}</td>
        </tr>
        """

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

    # ✅ CSV 다운로드
    csv_df = pd.DataFrame([{k: r[k] for k in ["파일명", "브랜드명", "품번"]} for r in results])
    csv = csv_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")


