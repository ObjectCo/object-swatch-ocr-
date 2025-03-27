import streamlit as st
import pandas as pd
from PIL import Image
import io
import base64
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image

st.set_page_config(page_title="Object Swatch OCR", layout="wide")

# JS modal & style
st.markdown("""
    <style>
    .modal {
        display: none; position: fixed; z-index: 999;
        padding-top: 60px; left: 0; top: 0;
        width: 100%; height: 100%;
        overflow: auto; background-color: rgba(0,0,0,0.8);
    }
    .modal-content {
        margin: auto; display: block;
        max-width: 90%;
    }
    .close {
        position: absolute; top: 20px; right: 35px;
        color: #fff; font-size: 40px; font-weight: bold;
        cursor: pointer;
    }
    .thumb {
        height: 35px; cursor: pointer;
    }
    </style>
    <div id="imgModal" class="modal">
        <span class="close" onclick="document.getElementById('imgModal').style.display='none'">&times;</span>
        <img class="modal-content" id="modalImg">
    </div>
""", unsafe_allow_html=True)

# 타이틀 및 로고
st.image("https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg", width=140)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 브랜드명과 품번을 자동 인식하여 리스트로 출력합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(i_file):
        image = Image.open(i_file).convert("RGB")
        image.thumbnail((300, 300))
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        result = extract_info_from_image(image, filename=i_file.name)
        unique_id = i_file.name.replace(".", "").replace(" ", "").replace("/", "_")
        return {
            "썸네일": f"""
                <div>
                    <img class='thumb' id='thumb-{unique_id}' src='data:image/png;base64,{img_data}'>
                    <script>
                        const thumbElem = document.getElementById("thumb-{unique_id}");
                        if (thumbElem) {{
                            thumbElem.addEventListener("click", () => {{
                                const modal = document.getElementById("imgModal");
                                const modalImg = document.getElementById("modalImg");
                                modal.style.display = "block";
                                modalImg.src = "data:image/png;base64,{img_data}";
                            }});
                        }}
                    </script>
                </div>
            """,
            "파일명": i_file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", []))
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(process_image, f): f.name for f in uploaded_files}
        for i, future in enumerate(concurrent.futures.as_completed(future_map)):
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "썸네일": "❌",
                    "파일명": future_map[future],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}"
                })
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")
    st.markdown("아래 결과는 엑셀에 **복사 & 붙여넣기** 가능합니다.")

    # HTML 테이블 생성
    html = "<table style='border-collapse: collapse; width: 100%; font-size: 14px;'>"
    html += "<thead><tr><th>썸네일</th><th>파일명</th><th>브랜드명</th><th>품번</th></tr></thead><tbody>"
    for r in results:
        html += f"<tr><td>{r['썸네일']}</td><td>{r['파일명']}</td><td>{r['브랜드명']}</td><td>{r['품번']}</td></tr>"
    html += "</tbody></table>"

    # 테이블 렌더링
    st.markdown(f"""
        <div style='width: 100%; max-width: 100%; overflow-x: auto; padding: 6px 0;'>
        {html}
        </div>
    """, unsafe_allow_html=True)

    # CSV 다운로드
    csv_df = pd.DataFrame([{k: r[k] for k in ["파일명", "브랜드명", "품번"]} for r in results])
    csv = csv_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")

