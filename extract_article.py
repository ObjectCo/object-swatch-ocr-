import re

def extract_article_numbers(text):
    # 1. 추출 대상: 브랜드명 또는 아티클 넘버 형태 (예: BD3991, AB-EX171, HT-21000 등)
    article_pattern = re.compile(r'\b(?:[A-Z]{2,5}[-]?\d{3,6}|\d{4,6})\b')

    # 2. 불필요한 키워드(대문자만으로 정규화하여 비교)
    exclude_keywords = {
        'JAPAN', 'TOKYO', 'OSAKA', 'WASHABLE', 'COTTON', 'LINEN', 'LABEL',
        'WARM', 'COOL', 'WATER', 'DESIGN', 'COLOR', 'SIZE', 'COMPO',
        'STRETCH', 'EFFECT', 'RESISTANT', 'QUALITY', 'VINTAGE', 'TEXTILE',
        'MADE', 'BANSHU-ORI', 'TEL', 'FAX', 'URL', 'CO', 'LTD', 'INC', 'NO',
        'ARTICLE', 'PLEASE', 'ATTENTION', 'WE', 'OK', 'COLORS', 'PROTECTION',
        'JACKET', 'PANTS', '2WAY', 'DEODORANT', 'TRANSPARENT', 'PREF', 'ID',
        'BKBK', 'KI', 'WH', 'MBK', 'CA', 'BO', 'M1', 'M2', 'M3', 'M4', 'M5',
        'M6', 'M7', 'M8', 'M14', 'M21', 'M34', 'M11', 'M13', 'M20', 'M22', 'M23',
        'COMPOSITION', 'CONSTRUCTION'
    }

    # 3. 전화번호/우편번호 등 제거
    phone_pattern = re.compile(r'\d{2,4}-\d{2,4}-\d{2,4}|\d{3}-\d{4}|\d{7,}')

    # 4. 필터링
    raw_tokens = re.findall(article_pattern, text)
    filtered = []
    for token in raw_tokens:
        if phone_pattern.match(token):
            continue
        if token.upper() in exclude_keywords:
            continue
        filtered.append(token)

    return list(set(filtered))  # 중복 제거

