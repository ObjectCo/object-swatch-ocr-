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
    "OHARAYA",
    "ROCK'N ROLL",
}

# 불필요 키워드 제거용
EXCLUDE_KEYWORDS = {
    "JAPAN", "TOKYO", "OSAKA", "WASHABLE", "COTTON", "LINEN", "LABEL", "WARM", "COOL",
    "WATER", "DESIGN", "COLOR", "SIZE", "COMPO", "STRETCH", "EFFECT", "RESISTANT",
    "QUALITY", "VINTAGE", "TEXTILE", "MADE", "BANSHU-ORI", "TEL", "FAX", "INC", "LTD",
    "CO", "NO", "ARTICLE", "HTTPS", "WWW", "URL", "ATTENTION", "PLEASE", "WE", "ARE",
    "THE", "AND", "IN", "OF", "WITH", "FOR", "ON", "BY", "FSCC", "TP", "PS", "C/#",
    "C/", "C#", "CODE", "E-MAIL", "INFO", "MM", "CM", "M", "G/M", "GSM", "MADE IN", "㈱"
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
    lines = text.splitlines()
    candidates = []

    article_pattern = re.compile(
        r'\b(?:[A-Z]{1,5}-)?[A-Z]{1,5}[-]?\d{3,6}(?:[-]\d{1,3})?\b|\b[A-Z]{2,10}\d{3,6}\b|\b\d{5,6}\b'
    )

    for line in lines:
        # 불필요 키워드가 포함된 줄 전체 스킵
        if any(skip in line.upper() for skip in EXCLUDE_KEYWORDS):
            continue

        matches = article_pattern.findall(line)
        for token in matches:
            token_clean = token.strip().upper()

            # 전화번호 포맷 제거
            if re.match(r"\d{2,4}-\d{2,4}-\d{2,4}", token_clean):
                continue

            # 너무 짧은 숫자, 연도 등 제거
            if re.fullmatch(r"\d{4}", token_clean) and not re.search(r"[A-Z]", token_clean):
                continue

            # 키워드 포함된 단일 토큰 제거
            if any(skip in token_clean for skip in EXCLUDE_KEYWORDS):
                continue

            candidates.append(token_clean)

    return list(set(candidates))  # 중복 제거

# 최종 결과 반환 함수
def extract_article_and_brand(text):
    brands = extract_brands(text)
    articles = extract_article_numbers(text)
    return {
        "brands": brands,
        "articles": articles
    }
