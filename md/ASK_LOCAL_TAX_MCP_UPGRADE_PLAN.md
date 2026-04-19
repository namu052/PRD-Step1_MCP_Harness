# ask_local_tax 검색 정확도 + 수집 범위 + 결과 품질 전면 강화 플랜 v4

> 작성일: 2026-04-05  
> **구현 완료: 2026-04-05**  
> 대상: MCP Tool `ask_local_tax` (및 `search_olta`)

---

## 1. 현재 파이프라인 흐름과 문제점

### 현재 흐름

```
질문 → LLM 키워드 추출 → keywords를 그대로 OLTA 검색 → 결과 랭킹 → 답변
```

### 문제점 4가지

| # | 문제 | 원인 | 영향 |
|---|------|------|------|
| 1 | 검색어 품질 | LLM이 `["상속", "1가구", "1주택"]` 같은 단편 키워드만 생성 | OLTA에서 관련 없는 결과 대량 수집 |
| 2 | 검색 횟수 부족 | `queries[:2]`만 BBS 검색에 사용 | 첫 키워드가 빗나가면 전체 실패 |
| 3 | 서브게시판 미활용 | BBS 통합 검색만 수행, 개별 게시판 미탐색 | 질의응답/지방세상담 등 핵심 게시판 누락 |
| 4 | 노이즈 자료 | 관련도 하한 필터 없이 40건 전체를 LLM에 전달 | 무관 자료가 답변 품질 저하 |

---

## 2. 수정 계획 개요

```
A. 검색어 생성 엔진 (Search Query Engine)
B. 크롤러 검색 경로 수정 (Crawler Search Path)
C. BBS 서브게시판 깊이 탐색 (BBS Deep Search)
D. 랭킹 품질 개선 (Ranking Quality)
E. MCP 파이프라인 통합 + 재시도 (Pipeline Integration)
F. 설정값 조정 (Configuration)
```

---

## 3. 상세 설계

### A. 검색어 생성 엔진

#### A-1. LLM 프롬프트 재설계 (`search_extraction_prompt.py`)

**현재 프롬프트 문제**: "핵심 세목과 쟁점을 분리 추출"이라는 지시가 단편 키워드만 생성

**변경: 4가지 검색 전략을 구체 예시와 함께 지시**

```python
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
- primary_topic: 질문의 주요 쟁점 1개"""
```

**스키마 확장**:

```python
KEYWORD_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "search_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "OLTA 검색창에 입력할 조합 검색어 3~4개 (각각 다른 전략)"
        },
        "query_strategies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "각 search_queries가 어떤 전략으로 만들어졌는지 (전략1~4)"
        },
        "keywords": {"type": "array", "items": {"type": "string"}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "legal_refs": {"type": "array", "items": {"type": "string"}},
        "primary_tax_type": {"type": "string"},
        "primary_topic": {"type": "string"},
    },
    "required": ["search_queries", "keywords", "synonyms", "legal_refs"],
    "additionalProperties": False,
}
```

- `query_strategies`는 디버깅/로그용 (어떤 전략이 효과적이었는지 추적)

---

#### A-2. SearchPlan 모델 확장 (`search_service.py`)

**신규 필드 4개 추가**:

```python
@dataclass
class SearchPlan:
    # ── 기존 필드 (변경 없음) ──
    question_type: str
    categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    detected_year: int | None = None
    prefer_latest: bool = True
    analysis_focus: list[str] = field(default_factory=list)
    collection_focus: list[str] = field(default_factory=list)
    
    # ── 신규 필드 ──
    search_queries: list[str] = field(default_factory=list)      # OLTA 검색에 실제 사용할 조합 검색어
    primary_tax_type: str = ""                                     # 주요 세목 → BBS 우선순위 결정
    primary_topic: str = ""                                        # 주요 쟁점 → BBS 우선순위 결정
    priority_bbs_boards: list[str] = field(default_factory=list)  # 우선 탐색할 BBS 게시판
```

---

#### A-3. `_llm_extract()` 반환값 확장 (`search_service.py:106`)

**현재**: keywords/synonyms/legal_refs만 추출, `list[str]` 반환  
**변경**: search_queries, primary_tax_type, primary_topic도 함께 추출, `dict` 반환

```python
async def _llm_extract(self, question: str) -> dict:
    """LLM에서 키워드 + 검색어 조합 + 세목/쟁점 한 번에 추출"""
    # ... OpenAI 호출 (기존과 동일) ...
    return {
        "search_queries": payload.get("search_queries", []),
        "keywords": combined_keywords,  # 기존 로직 유지
        "primary_tax_type": payload.get("primary_tax_type", ""),
        "primary_topic": payload.get("primary_topic", ""),
    }
```

- `build_search_plan()`에서 이 dict를 받아 `SearchPlan` 필드에 매핑
- LLM 호출 1회로 키워드+검색어+세목+쟁점을 동시 추출 (추가 API 비용 없음)

---

#### A-4. Fallback 검색어 자동 조합 (`search_service.py` 신규 메서드)

LLM이 `search_queries`를 빈 배열로 반환하거나 호출 실패 시:

```python
def _build_fallback_queries(self, question: str, keywords: list[str]) -> list[str]:
    queries = []
    
    # 전략1: 불용어 제거 축약 (30자 이내)
    stopwords = "을를이가의은는도에서으로하고있는다줘알려설명해대해"
    compact = question
    for sw in stopwords:
        compact = compact.replace(sw, " ")
    compact = re.sub(r"\s+", " ", compact).strip()
    if 5 <= len(compact) <= 30:
        queries.append(compact)
    elif len(compact) > 30:
        queries.append(compact[:30].rsplit(" ", 1)[0])
    
    # 전략2: 세목 + 쟁점 조합
    tax_found = [t for t in TAX_TERMS if t in question]
    topic_found = [t for t in TOPIC_TERMS if t in question]
    if tax_found and topic_found:
        queries.append(f"{tax_found[0]} {topic_found[0]}")
    elif tax_found:
        queries.append(tax_found[0])
    
    # 전략3: LLM keywords 상위 3개 연결
    if len(keywords) >= 2:
        queries.append(" ".join(keywords[:3]))
    
    # 전략4: 법령 조문 + 세목
    legal_ref = re.search(r"제\d+조(?:의\d+)?", question)
    if legal_ref:
        tax = tax_found[0] if tax_found else "지방세"
        queries.append(f"지방세법 {legal_ref.group()} {tax}")
    
    # 중복 제거 + 최대 4개
    seen = set()
    result = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            result.append(q)
    return result[:4]
```

---

#### A-5. 질문 유형별 BBS 우선순위 게시판 매핑 (`search_service.py` 신규 메서드)

```python
_BBS_PRIORITY_MAP = {
    "감면·적용요건형": ["질의응답", "지방세상담", "실무편람", "FAQ", "참고자료"],
    "판례·결정례 비교형": ["쟁송사무지원 사례", "참고자료", "쟁송사무위크숍 자료", "질의응답"],
    "유권해석 중심형": ["질의응답", "지방세상담", "참고자료", "실무편람"],
    "절차·기한형": ["질의응답", "FAQ", "매뉴얼", "실무편람", "이용안내 Q&A"],
    "환급·구제형": ["질의응답", "지방세상담", "쟁송사무지원 사례", "참고자료"],
    "일반 종합형": ["질의응답", "지방세상담", "실무편람", "참고자료", "FAQ"],
}

def _select_priority_bbs_boards(self, question_type: str, primary_tax_type: str) -> list[str]:
    boards = list(self._BBS_PRIORITY_MAP.get(
        question_type, self._BBS_PRIORITY_MAP["일반 종합형"]
    ))
    
    # 세목에 따라 추가 부스트
    if primary_tax_type in ("취득세", "재산세"):
        if "시가표준액 조정기준" not in boards:
            boards.append("시가표준액 조정기준")
    if "쟁송" in primary_tax_type or "불복" in primary_tax_type:
        if "전국단위사건 알림방" not in boards:
            boards.insert(2, "전국단위사건 알림방")
    
    return boards[:5]
```

---

#### A-6. `build_search_plan()` 통합 흐름 (`search_service.py:80`)

```python
async def build_search_plan(self, question: str) -> SearchPlan:
    # ... 기존 전처리 ...
    
    if settings.search_use_llm_extraction:
        extracted = await self._llm_extract(normalized)  # dict 반환
        keywords = extracted["keywords"]
        search_queries = extracted.get("search_queries", [])
        primary_tax_type = extracted.get("primary_tax_type", "")
        primary_topic = extracted.get("primary_topic", "")
    else:
        keywords = self._extract_without_llm(normalized)
        search_queries = []
        primary_tax_type = ""
        primary_topic = ""
    
    # search_queries가 없으면 fallback
    if not search_queries:
        search_queries = self._build_fallback_queries(normalized, keywords)
    
    # 질문 유형 분류 + BBS 우선순위
    question_type = self._classify_question_type(normalized)
    priority_bbs_boards = self._select_priority_bbs_boards(question_type, primary_tax_type)
    
    return SearchPlan(
        # ... 기존 필드 ...
        search_queries=search_queries[:settings.search_max_queries],
        primary_tax_type=primary_tax_type,
        primary_topic=primary_topic,
        priority_bbs_boards=priority_bbs_boards,
    )
```

---

### B. 크롤러 검색 경로 수정

#### B-1. `search()` 시그니처 확장 (`crawler_service.py:1110`)

```python
async def search(
    self,
    session,
    queries: list[str],
    categories: list[str] | None = None,
    on_progress: ProgressCallback = None,
    priority_bbs_boards: list[str] | None = None,  # 신규
) -> list[CrawlResult]:
```

- `priority_bbs_boards`를 `_real_search()`까지 전달

---

#### B-2. `_real_search()` 검색어 균등 배분 (`crawler_service.py:1124`)

**현재 문제점 3가지**:
1. `queries[0]`에 `olta_max_pages_per_collection=3` 전부, `queries[1:]`은 절반
2. `len(cards_by_id) >= olta_max_detail_fetch * 3`이면 나머지 검색어 스킵
3. BBS에 `queries[:2]`만 전달

**변경**:

```python
async def _real_search(self, queries, categories, context, on_progress, priority_bbs_boards):
    settings = get_settings()
    page = await context.new_page()
    page.set_default_timeout(settings.playwright_timeout)
    try:
        cards_by_id: dict[str, SearchCard] = {}
        
        # ── 변경점 1: 검색어별 균등 페이지 배분 ──
        base_limit = settings.olta_max_pages_per_collection or 4
        per_query_limit = max(2, base_limit // max(1, len(queries)))
        
        for index, query in enumerate(queries):
            # ── 변경점 2: 조기 종료 조건 완화 ──
            if index > 0 and len(cards_by_id) >= settings.olta_max_detail_fetch * 5:
                logger.info("Early stop: %d cards after %d queries", len(cards_by_id), index)
                break

            cards = await self._collect_query_cards(
                page, query, categories, per_query_limit, on_progress=on_progress,
            )
            for card in cards:
                existing = cards_by_id.get(card.id)
                if not existing or card.relevance_score > existing.relevance_score:
                    cards_by_id[card.id] = card
            
            logger.info("Query '%s': %d cards (total %d)", query[:30], len(cards), len(cards_by_id))

        # ... 상세 수집 ...

        # ── 변경점 3: BBS에 전체 검색어 + 우선순위 게시판 전달 ──
        if settings.olta_bbs_enabled and self._olta_logged_in:
            bbs_results = await self._search_all_bbs_boards(
                context,
                queries,  # 기존 queries[:2] → 전체
                page=shared_page,
                on_progress=on_progress,
                priority_boards=priority_bbs_boards,  # 신규
            )
            # ...
```

---

#### B-3. 검색어별 수집 출처 추적

**`SearchCard`에 `source_query` 필드 추가**:

```python
@dataclass
class SearchCard:
    # ... 기존 필드 ...
    source_query: str = ""  # 이 카드를 수집한 검색어
```

**`CrawlResult`에 `source_query` 필드 추가** (`models/schemas.py:117`):

```python
class CrawlResult(BaseModel):
    # ... 기존 ...
    source_query: str = ""  # 이 자료를 수집한 검색어
```

- `_collect_query_cards()`에서 `query`를 각 card에 기록
- `_fetch_detail()`에서 card의 `source_query`를 result에 전달
- 기본값 빈 문자열 → 기존 코드에 영향 없음

---

### C. BBS 서브게시판 깊이 탐색

#### C-1. `_search_all_bbs_boards()` 2단계 아키텍처 (`crawler_service.py:1938`)

**현재**: 통합 검색 1단계만  
**변경**: 2단계 + 우선순위 게시판 개별 탐색

```python
async def _search_all_bbs_boards(
    self,
    auth_context: BrowserContext,
    queries: list[str],
    page: Page | None = None,
    on_progress: ProgressCallback = None,
    priority_boards: list[str] | None = None,  # 신규
) -> list[CrawlResult]:
    settings = get_settings()
    
    # ━━ Stage 1: 통합 검색 (기존 로직) ━━
    all_results = await self._bbs_unified_search(auth_context, queries, page, on_progress)
    
    # ━━ Stage 2: 우선순위 게시판 개별 탐색 (신규) ━━
    if priority_boards and len(all_results) < settings.olta_bbs_fallback_threshold:
        stage2_results = await self._bbs_priority_board_search(
            auth_context, queries, priority_boards, all_results, on_progress,
        )
        seen_ids = {r.id for r in all_results}
        for r in stage2_results:
            if r.id not in seen_ids:
                all_results.append(r)
                seen_ids.add(r.id)
    
    return all_results
```

---

#### C-2. Stage 1 리팩토링: `_bbs_unified_search()`

기존 `_search_all_bbs_boards()` 본문을 그대로 분리 (리팩토링만, 로직 변경 없음)  
변경점: 통합 검색 페이지 수 동적 조정

```python
# 검색어당 2페이지, 최소 4페이지, 최대 10페이지
max_pages = min(10, max(4, len(queries) * 2))
```

---

#### C-3. Stage 2 신규: `_bbs_priority_board_search()`

```python
async def _bbs_priority_board_search(
    self,
    auth_context: BrowserContext,
    queries: list[str],
    priority_boards: list[str],
    existing_results: list[CrawlResult],
    on_progress: ProgressCallback = None,
) -> list[CrawlResult]:
    """우선순위 게시판에 대해 개별 검색을 수행하여 보충 자료 수집"""
    results: list[CrawlResult] = []
    seen_ids = {r.id for r in existing_results}
    
    # Stage 1에서 이미 수집된 게시판 파악
    collected_boards = set()
    for r in existing_results:
        for bbs_id, label in self._BBS_ID_LABEL_MAP.items():
            if bbs_id in r.id:
                collected_boards.add(label)
    
    # Stage 1에서 0건이었던 우선순위 게시판만 개별 검색
    target_boards = [b for b in priority_boards if b not in collected_boards][:3]
    
    for board_name in target_boards:
        await self._emit_collection_progress(
            on_progress, board_name="기타",
            sub_board_name=f"{board_name}(보충)", status="collecting",
        )
        
        for query in queries[:2]:
            board_results = await self._search_single_bbs_board(
                auth_context, query, board_name,
            )
            for r in board_results:
                if r.id not in seen_ids:
                    results.append(r)
                    seen_ids.add(r.id)
        
        await self._emit_collection_progress(
            on_progress, board_name="기타",
            sub_board_name=f"{board_name}(보충)",
            collected_count=len([r for r in results if board_name in r.type]),
            status="done",
        )
    
    return results
```

- 최대 3개 게시판 x 2개 검색어 = 6회 추가 검색
- `_search_single_bbs_board()`는 이미 완성된 메서드 (2106행~)

---

#### C-4. BBS 상세 수집 병렬화 (`crawler_service.py:2060`)

**현재**: 순차 수집

```python
for link in links:
    result = await self._fetch_bbs_detail_direct(auth_context, link["url"], ...)
```

**변경**: Semaphore 기반 병렬

```python
semaphore = asyncio.Semaphore(settings.olta_bbs_concurrency)

async def fetch_one(link: dict) -> CrawlResult | None:
    async with semaphore:
        return await self._fetch_bbs_detail_direct(
            auth_context, link["url"], link["title"], link["card_id"], board_label,
        )

fetch_results = await asyncio.gather(
    *(fetch_one(link) for link in links),
    return_exceptions=True,
)
for item in fetch_results:
    if isinstance(item, CrawlResult):
        all_results.append(item)
        board_result_count += 1
```

- 병렬도: `olta_bbs_concurrency=3` (이미 설정값 존재, 현재 미사용)
- 예상 속도: 20건 순차(60초) → 3병렬(~20초)

---

### D. 랭킹 품질 개선

#### D-1. 임베딩 랭킹에 search_queries 활용 (`embedding_service.py`)

**`rank_results()` 시그니처 확장**:

```python
async def rank_results(
    self,
    question: str,
    results: list[CrawlResult],
    top_k: int | None = None,
    preferred_year: int | None = None,
    prefer_latest: bool = True,
    search_queries: list[str] | None = None,  # 신규
) -> list[CrawlResult]:
```

**`_term_overlap_score()` 강화**:

```python
def _term_overlap_score(
    self,
    question: str,
    result: CrawlResult,
    search_queries: list[str] | None = None,
) -> float:
    # 기존: 질문 원문 term만
    question_terms = self._tokenize(question)
    # 신규: search_queries의 term도 추가
    if search_queries:
        for sq in search_queries:
            question_terms.update(self._tokenize(sq))
    
    haystack = f"{result.title} {result.preview} {result.content[:600]}".lower()
    return float(sum(1 for term in question_terms if term in haystack))
```

- search_queries에 포함된 실무 용어/법령 용어도 매칭에 반영

---

#### D-2. 관련도 하한 필터 (`mcp_server.py`)

랭킹 직후, LLM에 전달하기 전 노이즈 제거:

```python
if len(ranked) > 5:
    min_score = ranked[0].relevance_score * settings.min_relevance_ratio  # 0.3
    filtered = [r for r in ranked if r.relevance_score >= min_score]
    ranked = filtered if len(filtered) >= 5 else ranked[:max(5, len(filtered))]
```

- 자료 충분(15건+) → 최고 점수의 30% 미만 제거
- 자료 부족(5건 이하) → 전부 유지

---

### E. MCP 파이프라인 통합

#### E-1. `_run_full_pipeline()` 수정 (`mcp_server.py:209`)

```python
async def _run_full_pipeline(question: str) -> str:
    # ── Stage 1: 검색 계획 (search_queries 포함) ──
    search_plan = await search_service.build_search_plan(question)
    logger.info(
        "검색 계획: type=%s queries=%s tax=%s topic=%s bbs=%s",
        search_plan.question_type,
        search_plan.search_queries,
        search_plan.primary_tax_type,
        search_plan.primary_topic,
        search_plan.priority_bbs_boards[:3],
    )

    # ── Stage 2: OLTA 크롤링 (search_queries 사용) ──
    crawl_results = await crawler_service.search(
        session,
        search_plan.search_queries,               # ← keywords → search_queries
        search_plan.categories,
        priority_bbs_boards=search_plan.priority_bbs_boards,  # ← 신규
    )

    # ── Stage 2-B: 0건 시 fallback 재시도 ──
    if not crawl_results and search_plan.keywords:
        logger.info("1차 검색 0건 — fallback 검색어로 재시도")
        fallback_queries = search_service._build_fallback_queries(
            question, search_plan.keywords,
        )
        if fallback_queries != search_plan.search_queries:
            crawl_results = await crawler_service.search(
                session, fallback_queries, search_plan.categories,
            )
            search_plan.search_queries = fallback_queries  # 통계용

    if not crawl_results:
        return f"{login_note}OLTA에서 자료를 수집하지 못했습니다. ..."

    # ── Stage 3: 랭킹 (search_queries 전달) ──
    ranked = await embedding_service.rank_results(
        question,
        crawl_results,
        preferred_year=search_plan.detected_year,
        prefer_latest=search_plan.prefer_latest,
        search_queries=search_plan.search_queries,  # ← 신규
    )
    
    # ── Stage 3-B: 관련도 하한 필터 ──
    if len(ranked) > 5:
        min_score = ranked[0].relevance_score * get_settings().min_relevance_ratio
        filtered = [r for r in ranked if r.relevance_score >= min_score]
        ranked = filtered if len(filtered) >= 5 else ranked[:max(5, len(filtered))]

    # ── Stage 4~5: 근거 그루핑 + 답변 생성 (기존 동일) ──
```

---

#### E-2. `_run_search_pipeline()` 동일 적용 (`mcp_server.py:132`)

search_olta 도구도 동일하게 `search_queries` + `priority_bbs_boards` 전달.

---

#### E-3. 3단계 재시도 전략

```
1차: LLM 생성 search_queries로 검색
  ↓ 0건
2차: 규칙 기반 fallback_queries로 검색
  ↓ 0건
3차: 질문 원문 축약(30자)을 그대로 검색
  ↓ 0건
에러 메시지 반환
```

```python
# 3차 재시도
if not crawl_results:
    compact = re.sub(r"[?.,()에서을를이가의은는도에게로부터]", " ", question)
    compact = re.sub(r"\s+", " ", compact).strip()[:30]
    crawl_results = await crawler_service.search(session, [compact], search_plan.categories)
```

---

#### E-4. 결과 포매팅 상세화

```python
sections.append("\n\n---\n\n## 검색 분석")
sections.append(f"- 질문 유형: {search_plan.question_type}")
sections.append(f"- 주요 세목: {search_plan.primary_tax_type or '미지정'}")
sections.append(f"- 주요 쟁점: {search_plan.primary_topic or '미지정'}")
sections.append(f"- 검색어 조합:")
for i, q in enumerate(search_plan.search_queries, 1):
    sections.append(f"  {i}. \"{q}\"")
sections.append(f"- 우선 BBS 게시판: {', '.join(search_plan.priority_bbs_boards[:3]) or '기본'}")
sections.append(f"- 수집 범위: {', '.join(search_plan.collection_focus) or '전체'}")

# 검색어별 수집 기여도 (source_query 추적 시)
if any(r.source_query for r in ranked):
    query_counts = {}
    for r in ranked:
        sq = r.source_query or "미분류"
        query_counts[sq] = query_counts.get(sq, 0) + 1
    sections.append(f"\n## 검색어별 수집 기여도")
    for sq, count in sorted(query_counts.items(), key=lambda x: -x[1]):
        sections.append(f"  - \"{sq}\": {count}건")
```

---

### F. 설정값 조정 (`config.py`)

| 설정 | 현재값 | 변경값 | 이유 |
|------|--------|--------|------|
| `olta_max_pages_per_collection` | 3 | 4 | 균등 배분 시 여유 확보 |
| `olta_max_detail_fetch` | 20 | 25 | 검색어 증가로 후보 확대 |
| 신규 `search_max_queries` | — | 4 | search_queries 최대 개수 |
| 신규 `min_relevance_ratio` | — | 0.3 | 관련도 하한 (최고 대비 비율) |
| 신규 `olta_bbs_fallback_threshold` | — | 5 | BBS Stage 2 트리거 기준 |

---

## 4. 변경 파일 전체 목록

| # | 파일 | 변경 항목 | 변경 크기 |
|---|------|----------|----------|
| 1 | `backend/app/prompts/search_extraction_prompt.py` | A-1: 프롬프트 재설계 + 스키마 확장 | 소 (~30줄) |
| 2 | `backend/app/services/search_service.py` | A-2~A-6: SearchPlan 확장, _llm_extract 수정, fallback, BBS 우선순위 | 대 (~100줄+) |
| 3 | `backend/app/services/crawler_service.py` | B-1~B-3, C-1~C-5: 시그니처, 균등배분, BBS 2단계, 병렬화, source_query | 대 (~80줄+) |
| 4 | `backend/mcp_server.py` | E-1~E-4: 파이프라인 연결, 재시도, 필터, 포매팅 | 중 (~50줄+) |
| 5 | `backend/app/models/schemas.py` | D-1: CrawlResult.source_query 추가 | 소 (1줄) |
| 6 | `backend/app/services/embedding_service.py` | D-1~D-2: rank_results에 search_queries 반영 | 소 (~15줄) |
| 7 | `backend/app/config.py` | F: 설정값 3개 추가 + 2개 조정 | 소 (~5줄) |

### 건드리지 않는 파일

- `evidence_group_service.py` — 입력 자료 품질이 올라가면 자동 개선
- `evidence_summary_service.py` — 동일
- `llm_service.py` — 동일
- `grouped_answer_prompt.py` — 동일
- `verification/*` — MCP에서 미사용
- `openai_service.py` — 변경 불필요

---

## 5. 구현 순서 (의존성 기반)

```
1. config.py                       (설정값 추가)
2. models/schemas.py               (CrawlResult.source_query)
3. search_extraction_prompt.py     (프롬프트 + 스키마)
4. search_service.py               (SearchPlan 확장 + fallback + BBS 우선순위)
5. crawler_service.py              (검색어 경로 + BBS 2단계 + 병렬화)
6. embedding_service.py            (search_queries 반영)
7. mcp_server.py                   (파이프라인 통합 + 재시도 + 포매팅)
```

---

## 6. 예상 효과

| 지표 | 기존 | 변경 후 |
|------|------|--------|
| "상속 1가구 1주택 세율특례" | 관련 자료 0건 | 3~4개 조합 검색어로 다각도 수집 |
| "장애인 감면 공동등록" | 3건 (무관 자료) | 질의응답/지방세상담 우선 + fallback |
| BBS 수집 누락 | 통합 검색에서 빠진 게시판 미탐색 | Stage 2에서 우선순위 게시판 보충 |
| BBS 상세 수집 시간 | 순차 ~60초 | 3병렬 ~20초 |
| 노이즈 자료 | 40건 전체 LLM 전달 | 관련도 하한 필터로 정제 후 전달 |
| 1차 검색 실패 | 에러 반환 | 3단계 fallback으로 자동 재시도 |
| 디버깅 | 어떤 검색어가 효과적인지 불명 | source_query + 검색어별 기여도 표시 |

### 소요 시간 변화

| 시나리오 | 기존 | 변경 후 |
|---------|------|--------|
| 정상 검색 | 30~60초 | 40~70초 (검색어 증가) |
| 1차 실패 → fallback | 30~60초 (0건 반환) | 60~90초 (재시도로 결과 확보) |
| BBS 상세 수집 | ~60초 (순차) | ~20초 (병렬) |
