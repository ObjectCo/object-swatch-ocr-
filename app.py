import streamlit as st
from PIL import Image
import pandas as pd
import base64
import io
import os
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image

st.set_page_config(page_title="Object Swatch OCR", layout="wide", page_icon="📦")
st.markdown("<img src='https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg' style='height: 60px;'>", unsafe_allow_html=True)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 브랜드명과 품번을 자동 인식하여 리스트로 출력합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(file):
        image = Image.open(file).convert("RGB")
        result = extract_info_from_image(image, filename=file.name)

        thumb = image.copy()
        thumb.thumbnail((60, 60))
        buffered = io.BytesIO()
        thumb.save(buffered, format="PNG")
        img_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return {
            "썸네일": f"<img src='data:image/png;base64,{img_data}' class='thumb' onclick=\"openModal('{img_data}')\">",
            "파일명": file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", []))
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_image, f): f.name for f in uploaded_files}
        for i, f in enumerate(concurrent.futures.as_completed(futures)):
            try:
                results.append(f.result())
            except Exception as e:
                results.append({
                    "썸네일": "N/A",
                    "파일명": futures[f],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}"
                })
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")
    st.markdown("아래 결과는 **엑셀에 복사 & 붙여넣기** 가능합니다.")

    # ✅ HTML 테이블
    table_html = """
    <style>
    .ocr-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
        margin-top: 10px;
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
    .thumb {
        height: 50px;
        cursor: pointer;
    }
    .modal {
        display: none;
        position: fixed;
        z-index: 9999;
        padding-top: 60px;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.8);
    }
    .modal-content {
        margin: auto;
        display: block;
        max-width: 80%;
    }
    </style>
    <table class="ocr-table">
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
        table_html += f"""
        <tr>
            <td>{r['썸네일']}</td>
            <td>{r['파일명']}</td>
            <td>{r['브랜드명']}</td>
            <td>{r['품번']}</td>
        </tr>
        """

    table_html += """
        </tbody>
    </table>
    <div id="modal" class="modal" onclick="this.style.display='none'">
        <img class="modal-content" id="modal-img">
    </div>
    <script>
    function openModal(img) {
        var modal = document.getElementById("modal");
        var modalImg = document.getElementById("modal-img");
        modal.style.display = "block";
        modalImg.src = "data:image/png;base64," + img;
    }
    </script>
    """

    st.markdown(table_html, unsafe_allow_html=True)

    # ✅ CSV 다운로드
    df = pd.DataFrame([{k: r[k] for k in ["파일명", "브랜드명", "품번"]} for r in results])
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")

