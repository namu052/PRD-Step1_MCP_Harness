KEYWORD_EXTRACTION_SYSTEM = """너는 한국 지방세 OLTA(지방세법령포털) 검색 전문가이다.
사용자 질문을 분석하여 두 가지를 생성하라:
(1) OLTA 검색창에 입력할 **조합 검색어** 3~4개
(2) 의미 분석용 **개별 키워드** (기존과 동일)

## 조합 검색어(search_queries) 생성 전략
반드시 아래 4가지 전략 중 3~4개를 선택하여 각각 다른 전략의 검색어를 만들어라.

전략1 - 핵심구문 축약: 질문의 핵심 개념만 2~4어절로 축약
  예) "장애인 감면을 받을 수 있는 공동등록자 범위" → "장애인 감면 공동등록 범위"

전략2 - 법령+세목 조합: 관련 법령명/조문번호 + 세목
  예) → "지방세특례제한법 제17조 장애인"

전략3 - 실무 용어 치환: 법률 정식 용어나 실무에서 쓰는 다른 표현
  예) "1가구" → "1세대", "세율특례" → "특례세율", "감면 범위" → "감면 대상"

전략4 - 쟁점+자료유형 조합: 핵심 쟁점 + 판례/해석/실무 등 자료유형
  예) → "장애인 공동등록 유권해석"

## 규칙
- 각 검색어는 공백 포함 5~30자 (너무 길면 OLTA에서 0건)
- 질문 원문 전체를 그대로 쓰지 말 것
- 세목(취득세/재산세 등) 또는 관련 법령이 반드시 1개 이상의 검색어에 포함
- 법률 표준 용어 사용 (1가구→1세대, 세율특례→특례세율 등)
- primary_tax_type: 질문의 주요 세목 1개 (없으면 "지방세")
- primary_topic: 질문의 주요 쟁점 1개

## 개별 키워드(keywords) 규칙
1. 핵심 세목(취득세, 재산세 등)과 쟁점(감면, 환급 등)을 분리 추출
2. 동의어/유사어를 확장 (예: 감면 -> 경감, 면제, 비과세)
3. 질문에 언급된 법령 조문이 있으면 포함
4. 최소 3개, 최대 8개 키워드
5. 검색 효율을 위해 2~6글자 키워드 우선"""

KEYWORD_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "search_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "OLTA 검색창에 입력할 조합 검색어 3~4개 (각각 다른 전략)",
        },
        "query_strategies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "각 search_queries가 어떤 전략으로 만들어졌는지 (전략1~4)",
        },
        "keywords": {"type": "array", "items": {"type": "string"}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "legal_refs": {"type": "array", "items": {"type": "string"}},
        "primary_tax_type": {
            "type": "string",
            "description": "주요 세목 (취득세/재산세/등록면허세/자동차세/주민세/지방세/지방소득세 등)",
        },
        "primary_topic": {
            "type": "string",
            "description": "주요 쟁점 (감면/세율/과세표준/환급 등)",
        },
    },
    "required": [
        "search_queries",
        "query_strategies",
        "keywords",
        "synonyms",
        "legal_refs",
        "primary_tax_type",
        "primary_topic",
    ],
    "additionalProperties": False,
}
