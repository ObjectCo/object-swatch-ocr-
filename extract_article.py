import re

def extract_article_numbers(text):
    # 품번 포맷에 맞는 패턴 예시: 대문자/숫자 조합, 하이픈 포함 등
    pattern = r"\b[A-Z0-9\-/]{4,}\b"
    return re.findall(pattern, text)