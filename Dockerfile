FROM python:3.10-slim

WORKDIR /app

# 필수 패키지 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 🔥 여기에서 key.json을 반드시 복사해줘야 함
COPY . .
COPY key.json /app/key.json   # ✅ 핵심 라인 (꼭 있어야 함)

# 🔐 서비스 계정 키 환경 변수 등록
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/key.json"

EXPOSE 8080
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.enableCORS=false", "--server.address=0.0.0.0"]
