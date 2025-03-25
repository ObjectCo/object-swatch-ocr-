# Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 1. requirements 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2. 전체 앱 파일 복사 + 키 파일도 함께 포함
COPY . .

# 3. 환경 변수 설정 (key.json은 루트 경로에 있다고 가정)
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/key.json"

# 4. 포트 및 실행 명령
EXPOSE 8080
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.enableCORS=false", "--server.address=0.0.0.0"]
