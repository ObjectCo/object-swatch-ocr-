# postprocess.py
import re

# ✅ 품번 유효성 검사
def is_valid_article(article: str, company=None) -> bool:
    article = article.strip().upper()

    if article in ["TEL", "FAX", "HTTP", "WWW", "ARTICLE", "COLOR", "COMPOSITION"]:
        return False
    if "OCA" in article and re.match(r"OCA\d{3,}", article):
        return False
    if company and article == company.upper():
        return False
    if re.fullmatch(r"\d{1,2}", article):
        return False
    if re.fullmatch(r"C\d{2,3}%?", article):
        return False
    if len(article) < 3:
        return False
    if not re.search(r"[A-Z0-9]", article):
        return False
    if article.startswith("HTTP") or ".COM" in article:
        return False
    if re.fullmatch(r"\d{3}", article):
        return False

    return bool(re.search(r"[A-Z0-9/\-]{3,}", article)) or bool(re.search(r"\d{3,}", article))

# ✅ 오탐 가능성 높은 품번 감지
def is_suspicious_article(article: str) -> bool:
    a = article.upper()
    if re.search(r"(.)\1{2,}", a):  # 같은 문자 반복 3번 이상 (예: YGUUU003)
        return True
    if re.fullmatch(r"\d{2,3}[A-Z]{2,}X+\d{3}", a):  # 비정상 문자 반복 + X 반복
        return True
    if len(a) > 20:
        return True
    return False
