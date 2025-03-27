import streamlit as st
import pandas as pd
from PIL import Image
import base64
import io
import concurrent.futures
from gpt_vision_ocr import extract_info_from_image

st.set_page_config(page_title="Object Swatch OCR", layout="wide")
st.image("https://object-tex.com/_nuxt/img/logo-black.40d9d15.svg", width=150)
st.title("📦 Object Swatch OCR")
st.markdown("이미지를 업로드하면 회사명과 품번(Article No)을 자동으로 인식하고 리스트로 변환합니다.")

uploaded_files = st.file_uploader("이미지 업로드", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    st.subheader("⏳ 이미지 분석 중입니다...")
    results = []
    progress = st.progress(0)

    def process_image(i_file):
        image = Image.open(i_file)
        result = extract_info_from_image(image)

        # 썸네일 이미지 base64 인코딩
        thumb_img = image.copy()
        thumb_img.thumbnail((50, 50))  # 아주 작게
        buffer = io.BytesIO()
        thumb_img.save(buffer, format="PNG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode()

        # 썸네일 + 파일명 조합 (클릭 시 새 탭에 원본 이미지)
        file_display = f"""
            <a href="data:image/png;base64,{img_b64}" target="_blank">
                <img src="data:image/png;base64,{img_b64}" style="height:1em; vertical-align:middle;" />
            </a> <span style="vertical-align:middle;">{i_file.name}</span>
        """

        return {
            "파일명": file_display,
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
                    "파일명": future_map[future],
                    "브랜드명": "[ERROR]",
                    "품번": f"[ERROR] {str(e)}"
                })
            progress.progress((i + 1) / len(uploaded_files))

    df = pd.DataFrame(results)
    st.success("✅ 분석 완료!")

    st.markdown("아래 결과는 **엑셀에 복사 & 붙여넣기** 가능합니다.")
    st.markdown(
        df.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )

    csv = df.copy()
    csv["파일명"] = csv["파일명"].str.extract(r'>([^<]+)</span>')  # CSV 저장용: 파일명 텍스트만
    csv_data = csv.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv_data, file_name="swatch_ocr_results.csv", mime="text/csv")
