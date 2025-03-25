import re

# 사전에 수집한 브랜드명 (대소문자 무관 매칭)
KNOWN_BRANDS = {
    "KOMON KOBO",
    "ALLBLUE Inc.",
    "MATSUBARA CO.,LTD.",
    "COSMO TEXTILE",
    "AGUNINO",
    "HKK",
    "HK TEXTILE",
    "UNI TEXTILE",
}

# 불필요 키워드 제거용 패턴
EXCLUDE_KEYWORDS = {
    "JAPAN", "TOKYO", "OSAKA", "WASHABLE", "COTTON", "LINEN", "LABEL", "WARM", "COOL",
    "WATER", "DESIGN", "COLOR", "SIZE", "COMPO", "STRETCH", "EFFECT", "RESISTANT",
    "QUALITY", "VINTAGE", "TEXTILE", "MADE", "BANSHU-ORI", "TEL", "FAX", "INC", "LTD",
    "CO", "NO", "ARTICLE", "HTTPS", "WWW", "URL", "ATTENTION", "PLEASE", "WE", "ARE",
    "THE", "AND", "IN", "OF", "WITH", "FOR", "ON", "BY"
}

# 브랜드명 추출 함수
def extract_brands(text):
    found_brands = []
    for brand in KNOWN_BRANDS:
        if brand.lower() in text.lower():
            found_brands.append(brand)
    return found_brands

# 아티클 번호 추출 함수
def extract_article_numbers(text):
    # 패턴 예시: BD3991, HT-21000, WD8090, AB-EX171, 1025-600-3, 7025-610-3 등
    article_pattern = re.compile(r'\b(?:[A-Z]{1,5}-)?[A-Z]{1,5}[-]?\d{3,6}(?:[-]\d{1,3})?\b|\b\d{4,6}\b')

    matches = article_pattern.findall(text)
    results = []

    for token in matches:
        token_clean = token.strip().upper()

        # 제외 키워드 제거
        if token_clean in EXCLUDE_KEYWORDS:
            continue
        # 전화번호 등 제거
        if re.match(r"\d{2,4}-\d{2,4}-\d{2,4}", token_clean):
            continue
        # 너무 짧은 숫자 (ex: 2023)는 제외
        if re.fullmatch(r"\d{4}", token_clean) and not re.search(r"[A-Z]", token_clean):
            continue
        results.append(token_clean)

    return list(set(results))  # 중복 제거

# 최종 결과 반환 함수
def extract_article_and_brand(text):
    brands = extract_brands(text)
    articles = extract_article_numbers(text)
    return {
        "brands": brands,
        "articles": articles
    }
