import streamlit as st
import pandas as pd
from PIL import Image
import io
import base64
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image

st.set_page_config(page_title="Object Swatch OCR", layout="wide")

st.markdown("""
    <div style='display: flex; align-items: center; gap: 10px;'>
        <img src='https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg' style='height: 60px;'>
        <h1 style='margin: 0;'>📦 Object Swatch OCR</h1>
    </div>
    <p>이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.</p>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(file):
        image = Image.open(file)
        result = extract_info_from_image(image, filename=file.name)

        thumb = image.copy()
        thumb.thumbnail((60, 60))
        buffered = io.BytesIO()
        thumb.save(buffered, format="PNG")
        thumb_b64 = base64.b64encode(buffered.getvalue()).decode()

        full_img_b64 = base64.b64encode(file.read()).decode()

        return {
            "파일명": file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", [])),
            "썸네일": thumb_b64,
            "원본": full_img_b64
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_image, f) for f in uploaded_files]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            results.append(future.result())
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")
    st.markdown("아래 결과는 엑셀에 <strong>복사 & 붙여넣기</strong> 가능합니다.", unsafe_allow_html=True)

    # ✅ 결과 테이블
    table_html = """
    <style>
    .ocr-table-container {
        width: 100%;
        overflow-x: auto;
    }
    .ocr-table {
        border-collapse: collapse;
        width: 100%;
        min-width: 900px;
        font-size: 15px;
    }
    .ocr-table th, .ocr-table td {
        border: 1px solid #ccc;
        padding: 8px;
        text-align: left;
        vertical-align: middle;
    }
    .ocr-table th {
        background-color: #333;
        color: white;
    }
    .ocr-img {
        height: 50px;
        cursor: pointer;
    }
    </style>
    <div class="ocr-table-container">
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
        thumb_img = f"<img src='data:image/png;base64,{r['썸네일']}' class='ocr-img' onclick=\"window.open('data:image/png;base64,{r['원본']}', '_blank')\">"
        table_html += f"""
        <tr>
            <td>{thumb_img}</td>
            <td>{r['파일명']}</td>
            <td>{r['브랜드명']}</td>
            <td>{r['품번']}</td>
        </tr>
        """

    table_html += "</tbody></table></div>"
    st.markdown(table_html, unsafe_allow_html=True)

    # ✅ CSV 다운로드
    csv_df = pd.DataFrame([{
        "파일명": r["파일명"],
        "브랜드명": r["브랜드명"],
        "품번": r["품번"]
    } for r in results])
    csv = csv_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")
