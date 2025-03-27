import streamlit as st
import pandas as pd
from PIL import Image
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image
import base64
import io

st.set_page_config(page_title="Object Swatch OCR", layout="wide")
st.markdown(
    "<img src='https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg' style='height: 60px;'>",
    unsafe_allow_html=True
)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(i_file):
        image = Image.open(i_file).convert("RGB")
        result = extract_info_from_image(image, filename=i_file.name)

        # 썸네일용 base64 인코딩
        thumb = image.copy()
        thumb.thumbnail((40, 40))
        buffered = io.BytesIO()
        thumb.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return {
            "썸네일": f"<img src='data:image/png;base64,{img_b64}' style='height:30px'>",
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
                    "썸네일": "",
                    "파일명": future_map[future],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}"
                })
            progress.progress((i + 1) / len(uploaded_files))

    st.success("✅ 분석 완료!")
    st.markdown("아래 결과는 엑셀에 **복사 & 붙여넣기** 가능합니다.")

    df = pd.DataFrame(results)
    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    csv = pd.DataFrame([{k: r[k] for k in ["파일명", "브랜드명", "품번"]} for r in results])
    csv_data = csv.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv_data, file_name="swatch_ocr_results.csv", mime="text/csv")
