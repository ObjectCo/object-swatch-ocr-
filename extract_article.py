import re

def extract_article_numbers(text):
    # 브랜드명 패턴 (대문자 또는 첫 글자만 대문자인 단어들로 구성된 1~3단어 조합)
    brand_pattern = re.compile(r'\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}|[A-Z]{2,})\b')

    # 아티클 번호 패턴 (예: AB-EX171, BD3991, WD8090, HT-21000, 7025-610-3 등)
    article_pattern = re.compile(r'\b(?:[A-Z]{2,5}-?[A-Z]{0,3}\d{3,6}|\d{4,6})\b')

    # 제외할 일반 키워드
    exclude_keywords = {
        'JAPAN', 'TOKYO', 'OSAKA', 'MADE', 'TEL', 'FAX',
        'WASHABLE', 'COTTON', 'LINEN', 'POLYESTER', 'RAYON', 'TEXTILE',
        'STRETCH', 'LABEL', 'WARM', 'COOL', 'RESISTANT', 'WATER', 'REPELLENT',
        'HAND', 'WASH', 'DRY', 'UV', 'CUT', 'DESIGN', 'COLOR', 'SIZE',
        'COMPO', 'COMPOSITION', 'WEIGHT', 'QUALITY', 'VINTAGE',
        'EFFECT', 'TRICOT', 'NAME', 'CONSTRUCTION'
    }

    # 전화번호, 우편번호, 숫자 주소 제거
    phone_zip_pattern = re.compile(r'\d{2,4}-\d{2,4}-\d{2,4}|\d{3}-\d{4}|\d{6,}')

    # 전체 텍스트를 공백 단위로 나누어 토큰화
    tokens = re.findall(r'\b\w[\w\-\/]*\b', text)

    brand_names = set()
    article_numbers = set()

    for token in tokens:
        upper = token.upper()
        if phone_zip_pattern.match(token):
            continue
        if upper in exclude_keywords:
            continue
        if article_pattern.match(token):
            article_numbers.add(token)
        elif brand_pattern.match(token):
            brand_names.add(token)

    return list(brand_names.union(article_numbers))
