import streamlit as st
import openai
from PIL import Image
import io
import base64
import pandas as pd
import json
import os
import concurrent.futures

# 🔐 OpenAI API 키 설정 (환경변수에서 불러옴)
openai.api_key = os.environ.get("OPENAI_API_KEY")

# 📦 GPT Vision 이미지 분석 함수
def extract_info_from_image(image: Image.Image) -> dict:
    try:
        # 이미지 → base64 인코딩
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()

        # GPT-4o Vision 호출
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an OCR assistant. Extract the brand/company name and article number(s) from the uploaded fabric swatch image."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please extract the brand/company name and fabric article number(s).\n"
                                "- Return exactly in this format (JSON only):\n"
                                "{ \"company\": \"<Brand>\", \"article_numbers\": [\"<article1>\", \"<article2>\"] }\n"
                                "If not found, return { \"company\": \"N/A\", \"article_numbers\": [\"N/A\"] }"
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300,
        )

        result_text = response.choices[0].message.content.strip()

        # 👇 디버깅용 로그
        print("🧾 GPT 응답:", result_text)

        return json.loads(result_text)

    except json.JSONDecodeError as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] JSON decode error: {str(e)}"]
        }
    except Exception as e:
        return {
            "company": "[ERROR]",
            "article_numbers": [f"[ERROR] {str(e)}"]
        }


# 🌐 Streamlit 웹앱
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
        return {
            "파일명": i_file.name,
            "브랜드명": result.get("company", "N/A"),
            "품번": ", ".join(result.get("article_numbers", []))
        }

    # 🔄 병렬 처리로 속도 향상
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

    # 🧾 결과 출력
    df = pd.DataFrame(results)
    st.success("✅ 분석 완료!")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 결과 CSV 다운로드", data=csv, file_name="swatch_ocr_results.csv", mime="text/csv")
