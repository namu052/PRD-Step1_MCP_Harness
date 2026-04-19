# AI 지방세 지식인 시스템 — 프로젝트 보고서 자료

---

## 1. 전체 프로그램 흐름도

### 1-1. 사용자 질의 처리 전체 파이프라인

```
┌─────────────────────────────────────────────────────────────────────┐
│                         사용자 (공무원)                              │
│                    "취득세 감면 요건이 뭔가요?"                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP POST /api/chat
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite 8)                                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌───────────────┐   │
│  │ ChatInput │→│ useSSE()  │→│ chatStore    │→│ ChatPanel     │    │
│  │ (질문입력) │  │ (SSE연결)  │  │ (Zustand)    │  │ (답변표시)    │    │
│  └──────────┘  └───────────┘  └──────────────┘  └───────────────┘   │
│                      │                                ↕              │
│                      │ SSE Stream          ┌───────────────────┐    │
│                      │ (실시간 이벤트)      │ PreviewPanel      │    │
│                      │                     │ (출처카드 표시)     │    │
└──────────────────────┼─────────────────────┴───────────────────────┘
                       │
          ═════════════╧═══════════════
          ║   SSE (Server-Sent Events)  ║
          ═════════════╤═══════════════
                       │
┌──────────────────────┼──────────────────────────────────────────────┐
│  Backend (FastAPI)    │                                              │
│                      ▼                                              │
│  ┌─────────────── /api/chat ─────────────────────────────────────┐  │
│  │                                                                │  │
│  │  ══════════════════════════════════════════════════════════    │  │
│  │  ║  Stage 1: 자료 수집 (searching)                         ║    │  │
│  │  ══════════════════════════════════════════════════════════    │  │
│  │                                                                │  │
│  │  ① SearchService.build_search_plan()                          │  │
│  │     ├─ 질문 분류 (6가지 유형)                                   │  │
│  │     ├─ LLM 키워드 추출 (GPT-4o-mini)                           │  │
│  │     ├─ 검색어 생성 (최대 4개 쿼리)                               │  │
│  │     └─ 수집 카테고리 결정 (법령/해석/판례)                        │  │
│  │              │                                                  │  │
│  │              ▼                                                  │  │
│  │  ② CrawlerService.search()                                    │  │
│  │     ├─ OLTA 로그인 상태 확인                                    │  │
│  │     ├─ Playwright로 OLTA 웹사이트 크롤링                        │  │
│  │     │   ├─ 법령 검색 (law_search)                               │  │
│  │     │   ├─ 해석/심판 검색 (interpret_search)                     │  │
│  │     │   ├─ 판례/결정례 검색 (case_search)                        │  │
│  │     │   └─ BBS 게시판 검색 (질의응답, FAQ 등)                     │  │
│  │     └─ → CrawlResult[] (수집된 문서 목록)                        │  │
│  │              │                                                  │  │
│  │              ▼                                                  │  │
│  │  ③ EmbeddingService.rank_results()                             │  │
│  │     ├─ OpenAI Embedding API (text-embedding-3-small)           │  │
│  │     ├─ 코사인 유사도 + 키워드 겹침 + 연도 보너스 복합 스코어링      │  │
│  │     └─ 다양성 기반 상위 문서 선택 (top_k=40)                      │  │
│  │              │                                                  │  │
│  │              ▼                                                  │  │
│  │  ④ EvidenceGroupService.group()                                │  │
│  │     ├─ 임베딩 기반 유사 문서 군집화 (Union-Find)                   │  │
│  │     ├─ 세목/쟁점/제목 유사도로 그룹 결정                           │  │
│  │     └─ LLM으로 군집 검토 및 주제 정리                              │  │
│  │              │                                                  │  │
│  │              ▼                                                  │  │
│  │  ⑤ EvidenceSummaryService.summarize()                          │  │
│  │     ├─ 그룹별 대표 문서 선정                                     │  │
│  │     ├─ LLM으로 쟁점/결론/적용범위/예외 요약 (GPT-4o-mini)         │  │
│  │     └─ → EvidenceSlot[] (근거 묶음 슬롯)                         │  │
│  │                                                                │  │
│  │  ══════════════════════════════════════════════════════════    │  │
│  │  ║  Stage 2: 답변 생성 (answering)                         ║    │  │
│  │  ══════════════════════════════════════════════════════════    │  │
│  │                                                                │  │
│  │  ⑥ LLMService.generate_draft()                                │  │
│  │     ├─ Evidence Slot 기반 구조화된 프롬프트 구성                   │  │
│  │     ├─ GPT-4o로 최종 답변 생성                                   │  │
│  │     └─ 출처 인용 태그 [출처: xxx] 자동 삽입                       │  │
│  │              │                                                  │  │
│  │              ▼                                                  │  │
│  │  ⑦ 출처 카드 + 수집 요약 전송                                    │  │
│  │     ├─ sources 이벤트 (출처 카드 목록)                            │  │
│  │     ├─ crawl_summary 이벤트 (게시판별 수집 통계)                   │  │
│  │     └─ stage_change: done                                      │  │
│  │                                                                │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 1-2. SSE 이벤트 흐름 (시간순)

```
Backend                                          Frontend
   │                                                │
   │──── stage_change: "searching" ────────────────→│ StatusStepper: 자료수집 표시
   │──── notice: "질문 분석 완료: ..." ────────────→│ SystemMessage 추가
   │──── olta_login_required (조건부) ─────────────→│ OLTA 로그인 안내 표시
   │                                                │
   │──── crawl_progress (반복) ────────────────────→│ CrawlProgressBar 갱신
   │     { board_name, sub_board_name,              │
   │       collected_count, status }                │
   │                                                │
   │──── notice: "자료 수집 완료: N건..." ─────────→│ SystemMessage 추가
   │                                                │
   │──── stage_change: "answering" ────────────────→│ StatusStepper: 답변생성 표시
   │                                                │
   │──── token (반복, 5자씩) ──────────────────────→│ StreamingResponse 실시간 렌더링
   │     { token: "취득세" }                         │
   │                                                │
   │──── notice: "답변 생성 완료" ─────────────────→│ SystemMessage 추가
   │──── crawl_summary ────────────────────────────→│ CrawlSummaryCard 표시
   │──── sources ──────────────────────────────────→│ PreviewPanel에 출처카드 표시
   │──── stage_change: "done" ─────────────────────→│ FinalAnswerPopup 표시
   │                                                │
```

### 1-3. MCP 서버 연동 흐름

```
┌──────────────┐     stdio      ┌─────────────────┐     내부 호출     ┌──────────────────┐
│  Claude Code  │ ◄────────────► │  MCP Server      │ ──────────────→ │ Backend Services  │
│  (AI Agent)   │   JSON-RPC     │  (mcp_server.py) │                 │ (동일 서비스 재사용) │
└──────────────┘                └─────────────────┘                 └──────────────────┘

MCP 도구 목록:
  - search_olta         : OLTA 검색 + 크롤링 실행
  - ask_local_tax       : 질문 → 검색 → 답변 전체 파이프라인 실행
  - get_search_plan     : 검색 계획만 조회
  - get_document_content: 특정 문서 원문 조회
  - check_olta_login    : OLTA 로그인 상태 확인
  - open_olta_for_login : 로그인용 브라우저 열기
  - close_olta_browser  : 브라우저 종료
  - clear_cache         : 캐시 초기화
  - show_answer_in_browser: 답변을 HTML로 브라우저에 표시
```

---

## 2. 각 구성 요소 상세

### 2-1. 기술 스택 요약

| 구분 | 기술 | 버전/모델 | 역할 |
|------|------|-----------|------|
| **Frontend** | React | 19 | UI 프레임워크 |
| | Vite | 8 | 빌드 도구 + 개발 서버 |
| | Zustand | - | 전역 상태 관리 |
| | Tailwind CSS | 4 | 스타일링 |
| | MSW | - | Mock API (개발용) |
| **Backend** | FastAPI | - | REST API + SSE 서버 |
| | Playwright | - | OLTA 웹 크롤링 |
| | FAISS | - | 벡터 유사도 검색 |
| | Pydantic | v2 | 데이터 검증/설정 |
| **AI/LLM** | GPT-4o | - | 답변 생성, 검색어 추출 |
| | GPT-4o-mini | - | 검증, 요약, 검색어 추출 |
| | text-embedding-3-small | - | 문서 임베딩/랭킹 |
| **MCP** | FastMCP | - | Claude Code 연동 |

### 2-2. Frontend 구조

```
frontend/src/
├── App.jsx                          # 앱 진입점
├── main.jsx                         # React DOM 렌더링
├── index.css                        # Tailwind 기본 스타일
│
├── components/
│   ├── auth/
│   │   ├── CertSelector.jsx         # GPKI 인증서 선택
│   │   ├── GpkiLoginModal.jsx       # GPKI 로그인 모달
│   │   └── OltaLoginGuard.jsx       # OLTA 로그인 상태 가드
│   │
│   ├── chat/
│   │   ├── ChatInput.jsx            # 질문 입력 폼
│   │   ├── ChatMessage.jsx          # 개별 메시지 렌더링
│   │   ├── ChatPanel.jsx            # 좌측 채팅 영역 (50%)
│   │   ├── ConfidenceBadge.jsx      # 신뢰도 배지
│   │   ├── CrawlProgressBar.jsx     # 수집 진행률 표시
│   │   ├── FinalAnswerPopup.jsx     # 최종 답변 팝업
│   │   └── StreamingResponse.jsx    # 실시간 토큰 스트리밍 표시
│   │
│   ├── layout/
│   │   ├── AppShell.jsx             # 50:50 분할 레이아웃
│   │   ├── StatusStepper.jsx        # 단계 진행 표시기
│   │   └── TopBar.jsx               # 상단 내비게이션
│   │
│   └── preview/
│       ├── CrawlSummaryCard.jsx     # 수집 요약 카드
│       ├── PreviewPanel.jsx         # 우측 출처 패널 (50%)
│       ├── SourceCard.jsx           # 개별 출처 카드
│       └── SourceDetail.jsx         # 출처 상세 보기
│
├── hooks/
│   └── useSSE.js                    # SSE 연결 + 이벤트 핸들링
│
├── stores/
│   ├── authStore.js                 # GPKI 인증/세션 상태
│   └── chatStore.js                 # 채팅 메시지/스트리밍 상태
│
├── lib/
│   └── api.js                       # API URL 헬퍼
│
└── mocks/
    ├── browser.js                   # MSW 브라우저 워커
    ├── handlers.js                  # Mock API 핸들러
    └── data/
        ├── mockChatResponses.json   # Mock 채팅 응답
        └── mockSources.json         # Mock 출처 데이터
```

### 2-3. Backend 구조

```
backend/app/
├── main.py                          # FastAPI 앱 진입점
├── config.py                        # 전체 설정 (90+ 파라미터)
│
├── core/
│   ├── event_emitter.py             # SSE 이벤트 포매터
│   ├── security.py                  # 보안 미들웨어
│   └── session_manager.py           # 인메모리 세션 관리
│
├── models/
│   ├── schemas.py                   # 요청/응답 스키마
│   ├── evidence.py                  # EvidenceGroup, EvidenceSlot 모델
│   ├── session.py                   # 세션 모델
│   └── verification.py             # 검증 결과 모델
│
├── routers/
│   ├── auth.py                      # 인증 API (/api/auth/*)
│   └── chat.py                      # 채팅 API (/api/chat, /api/preview)
│
├── services/
│   ├── search_service.py            # 검색 계획 수립 + 키워드 추출
│   ├── crawler_service.py           # OLTA 웹 크롤링 (Playwright)
│   ├── embedding_service.py         # 임베딩 + 랭킹 (FAISS)
│   ├── evidence_group_service.py    # 근거 문서 군집화
│   ├── evidence_summary_service.py  # 근거 묶음 요약
│   ├── llm_service.py               # LLM 답변 생성/수정
│   ├── openai_service.py            # OpenAI API 래퍼
│   ├── gpki_service.py              # GPKI 인증 처리
│   ├── gap_analyzer_service.py      # 답변 갭 분석
│   └── web_search_service.py        # 웹 검색 (비활성)
│   │
│   └── verification/
│       ├── source_verifier.py       # 출처 유효성 검증
│       ├── content_verifier.py      # 내용(주장) 사실 검증
│       ├── grouped_answer_verifier.py # 근거묶음 반영 검증
│       ├── verification_aggregator.py # 신뢰도 종합 평가
│       └── final_generator.py       # 검증 후 최종 답변 정제
│
├── prompts/                         # LLM 프롬프트 템플릿
│   ├── search_extraction_prompt.py  # 검색어 추출 프롬프트
│   ├── evidence_summary_prompt.py   # 근거 요약 프롬프트
│   ├── grouped_answer_prompt.py     # 근거묶음 기반 답변 프롬프트
│   ├── grouped_verification_prompt.py # 근거묶음 검증 프롬프트
│   ├── revision_prompt.py           # 답변 수정 프롬프트
│   ├── gap_analysis_prompt.py       # 갭 분석 프롬프트
│   ├── stage1_prompt.py             # 1단계 초안 프롬프트
│   ├── stage2_source_prompt.py      # 출처 검증 프롬프트
│   ├── stage2_content_prompt.py     # 내용 검증 프롬프트
│   ├── stage2_final_prompt.py       # 최종 생성 프롬프트
│   └── web_draft_prompt.py          # 웹 검색 답변 프롬프트
│
└── mcp_server.py                    # MCP 서버 (Claude Code 연동)
```

### 2-4. 질문 분류 체계

시스템은 사용자 질문을 6가지 유형으로 자동 분류하여 최적의 검색 전략을 수립합니다.

| 질문 유형 | 분류 기준 키워드 | 수집 카테고리 우선순위 | BBS 우선 게시판 |
|-----------|-----------------|---------------------|----------------|
| **감면/적용요건형** | 감면, 비과세, 면제, 대상, 요건 | 법령 → 해석 → 판례 | 질의응답, 지방세상담, 실무편람 |
| **판례/결정례 비교형** | 판례, 판결, 심판, 결정례 | 판례 → 해석 | 쟁송사무지원, 참고자료 |
| **유권해석 중심형** | 유권해석, 법제처, 행안부, 해석 | 법령 → 해석 | 질의응답, 지방세상담 |
| **절차/기한형** | 신고, 납부, 기한, 절차, 제출 | 법령 → 해석 | 질의응답, FAQ, 매뉴얼 |
| **환급/구제형** | 환급, 경정청구, 불복, 구제 | 판례 → 해석 → 법령 | 질의응답, 쟁송사무지원 |
| **일반 종합형** | (위에 해당 없을 때) | 법령 → 해석 → 판례 | 질의응답, 지방세상담, 실무편람 |

### 2-5. 복합 스코어링 랭킹 시스템

문서 관련도 평가는 4가지 가중치를 복합 적용합니다.

```
최종 스코어 = (의미 유사도 × 0.6) + (키워드 겹침 × 0.2) + (검색 순위 × 0.1) + (연도 보너스 × 0.1)

┌─────────────────────┐
│  의미 유사도 (60%)    │  OpenAI Embedding → 코사인 유사도
├─────────────────────┤
│  키워드 겹침 (20%)    │  질문 토큰 ∩ 문서(제목+미리보기+본문600자)
├─────────────────────┤
│  검색 순위 (10%)      │  OLTA 원래 검색 순위 반영
├─────────────────────┤
│  연도 보너스 (10%)    │  특정 연도 질문: 해당 연도 ±12년 이내
│                      │  일반 질문: 최신 자료일수록 가산
└─────────────────────┘

+ 다양성 보장: 문서 유형별 쿼터(type당 최소 2건) → 편향 방지
```

### 2-6. 신뢰도 평가 시스템 (Verification Aggregator)

```
                    ┌─────────────────────────────────┐
                    │      종합 신뢰도 (Overall)       │
                    │   = 가중평균 + 패널티 캡          │
                    └─────────────┬───────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │ 주장 신뢰도 (55%) │  │ 출처 신뢰도 (25%) │  │ 슬롯 신뢰도 (20%) │
   │ claim_confidence │  │ source_confidence│  │ slot_confidence  │
   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
            │                    │                    │
    각 주장별 검증:        각 출처별 검증:        각 근거묶음별:
    - supported          - verified            - supported
    - partial            - expired             - partial
    - unsupported        - mismatch            - contradicted
    - hallucinated       - not_found           - unused

패널티 캡 (상한 제한):
  - 환각(hallucinated) 주장 존재     → 최대 0.34
  - 출처 검증 실패                    → 최대 0.40
  - 직접 출처 커버리지 < 50%          → 최대 0.55
  - 뒷받침 주장 비율 < 50%           → 최대 0.60

신뢰도 라벨:
  ≥ 0.85 → "매우 높음"  │  ≥ 0.70 → "높음"  │  ≥ 0.40 → "보통"  │  < 0.40 → "낮음"
```

---

## 3. 추가 분석 자료

### 3-1. 시스템 핵심 특장점

#### (1) 근거 기반 답변 생성 (Evidence-Grounded Answer Generation)
- 단순 LLM 답변이 아닌, **실제 OLTA 법령 포털의 자료를 실시간으로 크롤링**하여 근거를 확보한 후 답변을 생성합니다.
- 모든 답변에 `[출처: xxx]` 태그가 삽입되어, 사용자가 원문을 직접 확인할 수 있습니다.
- 이는 법률 분야에서 치명적인 **LLM 환각(Hallucination)** 문제를 구조적으로 완화합니다.

#### (2) 다중 LLM 모델 전략 (Multi-Model Strategy)
| 작업 | 모델 | 이유 |
|------|------|------|
| 최종 답변 생성 | GPT-4o | 최고 품질 답변 필요 |
| 검색어 추출, 검증, 요약 | GPT-4o-mini | 비용 효율 + 빠른 응답 |
| 문서 임베딩 | text-embedding-3-small | 벡터 검색 특화 |

→ **비용 최적화**: 핵심 답변에만 고비용 모델을 사용하고, 보조 작업은 경량 모델로 처리

#### (3) 실시간 SSE 스트리밍 UX
- 사용자는 **답변이 생성되는 과정을 실시간으로** 볼 수 있습니다.
- 수집 진행률, 단계 전환, 토큰 단위 답변 스트리밍을 통해 대기 시간에 대한 체감을 줄입니다.
- SSE 이벤트 타입: `stage_change`, `notice`, `crawl_progress`, `token`, `sources`, `crawl_summary`

#### (4) MCP(Model Context Protocol) 연동
- Claude Code에서 **MCP 도구로 직접 OLTA 검색/답변 생성을 호출**할 수 있습니다.
- AI Agent가 지방세 질의에 대해 자율적으로 자료를 수집하고 답변을 구성하는 워크플로우를 지원합니다.
- 웹 UI 없이도 CLI 환경에서 동일한 파이프라인을 사용할 수 있습니다.

### 3-2. 데이터 흐름별 LLM 호출 횟수 분석

하나의 질문 처리 시 발생하는 LLM API 호출:

```
질문 1건 처리 시 LLM 호출 횟수 (최소~최대)

1. 검색어 추출 ........................ 1회 (GPT-4o-mini)
2. 문서 임베딩 ........................ 1회 (embedding API, 배치)
3. 근거 군집 검토 ..................... N회 (GPT-4o-mini, N=군집 수, 보통 3~8개)
4. 근거 요약 ......................... M회 (GPT-4o-mini, M=군집 수, 사전요약 있으면 생략)
5. 최종 답변 생성 ..................... 1회 (GPT-4o)
──────────────────────────────────
합계: 약 3~12회 LLM 호출 / 질문 1건
```

### 3-3. 설정 파라미터 체계 (Config 분류)

`config.py`에 **90개 이상의 설정값**이 중앙 집중 관리되며, 환경변수(`.env`)로 오버라이드 가능합니다.

| 카테고리 | 파라미터 수 | 주요 예시 |
|----------|------------|----------|
| **OpenAI 모델** | 6개 | 모델명, 임베딩 모델 |
| **OLTA 크롤링** | 14개 | max_results, timeout, BBS 설정 |
| **임베딩/랭킹** | 7개 | 가중치(semantic 0.6, overlap 0.2 등) |
| **근거 그루핑** | 6개 | 유사도 임계값(0.84, 0.76), 제목 겹침 |
| **요약** | 3개 | 컨텐츠 제한, 최대 토큰 |
| **답변 생성** | 5개 | 온도(0.2), 최대 토큰(1800) |
| **신뢰도 평가** | 26개 | 패널티 계수, 캡 값, 가중치 |
| **검색** | 5개 | 최대 키워드(10), 최대 쿼리(4) |
| **인프라** | 3개 | 호스트, 포트, 세션 타임아웃(30분) |

### 3-4. 보안 및 인증 체계

```
┌─────────────────────────────────────────────┐
│              인증 흐름                        │
│                                             │
│  사용자 ──→ GPKI 인증서 선택                  │
│         ──→ 인증서 비밀번호 입력                │
│         ──→ Backend 검증 (/api/auth/login)    │
│         ──→ 세션 발급 (인메모리, 30분 TTL)      │
│         ──→ 이후 요청에 session_id 포함         │
│                                             │
│  OLTA 접근 ──→ Playwright 브라우저 세션 공유    │
│            ──→ 로그인 상태 확인 후 BBS 수집 결정 │
│            ──→ 미로그인 시: 법령/판례만 수집     │
│            ──→ 로그인 시: 전체(BBS 포함) 수집   │
└─────────────────────────────────────────────┘
```

### 3-5. 에러 처리 및 Fallback 전략

시스템은 각 단계에서 실패 시 graceful degradation을 적용합니다.

| 단계 | 실패 시나리오 | Fallback 전략 |
|------|-------------|--------------|
| 검색어 추출 | LLM API 실패 | 규칙 기반 키워드 추출 (TAX_TERMS + TOPIC_TERMS 매칭) |
| OLTA 크롤링 | 사이트 접속 불가 | Mock 데이터 반환 또는 빈 결과 |
| 임베딩 랭킹 | API 타임아웃(120s) | 키워드 기반 fallback 스코어링 |
| 근거 군집화 | 임베딩 실패 | 휴리스틱 기반 그루핑 (세목+쟁점 매칭) |
| 근거 요약 | LLM 실패 | 대표 문서 미리보기 텍스트 조합 |
| 답변 생성 | LLM 실패 | 수집 문서 목록 기반 간이 답변 |
| SSE 연결 | 네트워크 끊김 | 프론트엔드에서 에러 메시지 표시 |

### 3-6. 테스트 현황

```
backend/tests/
├── conftest.py                    # 공통 fixture
├── test_chat_pipeline.py          # 전체 파이프라인 통합 테스트
├── test_chat_progress.py          # 수집 진행률 이벤트 테스트
├── test_search.py                 # 검색 서비스 단위 테스트
├── test_crawler.py                # 크롤러 서비스 테스트
├── test_bbs_crawler.py            # BBS 게시판 크롤링 테스트
├── test_evidence_group_service.py # 근거 군집화 테스트
├── test_source_verifier.py        # 출처 검증 테스트
├── test_content_verifier.py       # 내용 검증 테스트
├── test_final_generator.py        # 최종 답변 생성 테스트
├── test_aggregator.py             # 신뢰도 종합 테스트
└── test_verification_pipeline.py  # 검증 파이프라인 통합 테스트

+ 루트 레벨 E2E/탐색 테스트:
  test_bbs_check.py, test_bbs_crawl.py, test_bbs_direct.py,
  test_bbs_live.py, test_bbs_structure.py, test_collection_stats.py,
  test_e2e_timing.py
```

### 3-7. 확장성 및 향후 개선 포인트

| 영역 | 현재 상태 | 개선 가능 방향 |
|------|----------|---------------|
| **세션 저장소** | 인메모리 (서버 재시작 시 소멸) | Redis 또는 DB 기반 영속 세션 |
| **벡터 DB** | FAISS (매 질문마다 새로 인덱싱) | 사전 인덱싱된 벡터 DB (Pinecone, Qdrant) |
| **검증 파이프라인** | 구현 완료, 현재 비활성 (3단계→2단계 축소) | 필요 시 재활성화 가능 |
| **사용자 인증** | GPKI 인증서 기반 | 통합 SSO 연동 가능 |
| **수평 확장** | 단일 서버, Playwright 인스턴스 1개 | 크롤러 워커 풀, 로드밸런서 |
| **캐싱** | MCP 서버에서만 5분 TTL 캐시 | 전역 질문-답변 캐시 레이어 도입 |
| **모니터링** | 로깅만 존재 | APM + 비용 추적 대시보드 |

---

## 부록: 주요 파일 코드량 참고

| 파일 | 라인 수 | 핵심 기능 |
|------|---------|----------|
| `crawler_service.py` | ~1,000+ | OLTA 크롤링 전체 로직 |
| `mcp_server.py` | ~500+ | MCP 도구 정의 |
| `search_service.py` | ~360 | 질문 분석 + 검색 계획 |
| `evidence_group_service.py` | ~390 | 근거 군집화 |
| `embedding_service.py` | ~270 | 임베딩 랭킹 |
| `config.py` | ~260 | 전체 설정 + OLTA 셀렉터 |
| `llm_service.py` | ~310 | LLM 답변 생성 |
| `verification_aggregator.py` | ~200 | 신뢰도 종합 |
| `chat.py` (router) | ~270 | SSE 스트리밍 오케스트레이션 |
| `chatStore.js` | ~200 | 프론트엔드 상태 관리 |
| `useSSE.js` | ~190 | SSE 이벤트 처리 |
