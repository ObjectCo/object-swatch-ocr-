import re

def extract_article_numbers(text):
    # 아티클 번호 추정 패턴 (예: BD3991, HT-21000, 7025-610-3 등)
    article_pattern = re.compile(r'\b[A-Z]{2,5}[-]?\d{3,6}\b|\b\d{4,6}\b')

    # 제외할 일반 키워드 리스트
    exclude_keywords = {
        'JAPAN', 'TOKYO', 'OSAKA', 'WASHABLE', 'COTTON', 'LINEN', 'LABEL',
        'WARM', 'COOL', 'WATER', 'DESIGN', 'COLOR', 'SIZE', 'COMPO',
        'STRETCH', 'EFFECT', 'RESISTANT', 'QUALITY', 'VINTAGE', 'TEXTILE',
        'MADE', 'BANSHU-ORI', 'TEL', 'FAX'
    }

    # 전화번호/우편번호 패턴 제거
    phone_pattern = re.compile(r'\d{2,4}-\d{2,4}-\d{2,4}|\d{3}-\d{4}|\d{7,}')
    
    # 필터링
    raw_tokens = re.findall(article_pattern, text)
    filtered = []
    for token in raw_tokens:
        if phone_pattern.match(token):
            continue
        if token.upper() in exclude_keywords:
            continue
        filtered.append(token)

    return list(set(filtered))  # 중복 제거
