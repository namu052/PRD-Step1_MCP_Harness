# STRUCTURE_RULES — 아키텍처 제약 (섹션 9)

> 본 규칙은 `tests/structure/`의 자동 검사와 1:1로 매핑된다. 규칙만 있고 검사 없는 항목은 효력이 없다.

## A. 아키텍처 규칙
1. **도메인 경계**: `backend/app/services/*`는 도메인별로 분리되고, 서비스 간 직접 import는 **router 경유** 또는 **명시적 facade**만 허용한다.
2. **레이어 구조(backend)**: `routers → services → repositories(미래) / external clients`. 반대 방향 import 금지.
3. **레이어 구조(frontend)**: `components → stores/hooks → lib`. 역방향 import 금지.
4. **허용 의존성**: UI 컴포넌트는 Zustand store를 직접 구독 가능. 컴포넌트가 `lib/`의 API 클라이언트를 호출할 수 있으나, 직접 `fetch`를 사용할 수는 없다.
5. **금지 의존성**:
   - `backend/app/services/**`가 FastAPI 객체(`Request`, `Response`) import 금지 — router에서 주입받기만.
   - `frontend/src/components/**`가 `lib/*` 외부의 네트워크 호출 직접 수행 금지.
   - 코어 코드가 `tests/` 모듈을 import 금지.
6. **Cross-cutting concerns 공식 유입 경로**: 로깅/트레이싱/인증은 각각 `backend/app/core/`의 단일 진입점을 사용. 개별 서비스가 로거 포매터·전역 상태를 재정의 금지.
7. **프롬프트/매직넘버**: 프롬프트는 `backend/app/prompts/` 내부 파일로, 매직넘버는 `backend/app/config.py` 한 곳. 인라인 하드코딩 금지.
8. **외부 네트워크**: 새 외부 호출은 `backend/app/services/<name>_service.py`에 래퍼 하나. 컴포넌트가 직접 호출 금지.
9. **파일 크기**: 200–400줄 목표, 800줄 상한.
10. **함수 크기**: 50줄 상한, 중첩 4단계 상한.

## B. 구조 검사 규칙(→ `tests/structure/` 구현 항목)
1. `test_layering.py` — import 그래프에서 역방향 edge 0개.
2. `test_services_no_fastapi_types.py` — `services/`에서 `fastapi.*` 심볼 등장 0개.
3. `test_components_no_fetch.py` — `src/components/` 안의 `fetch(`, `axios` 직접 호출 0개.
4. `test_prompt_constants_location.py` — prompt 상수 SCREAMING_SNAKE_CASE이며 `app/prompts/`에만.
5. `test_file_size.py` — 800줄 초과 파일 0개.
6. `test_function_size.py` — 50줄 초과 함수 0개, 또는 `# allow-long: reason` 주석 필요.
7. `test_no_absolute_paths_in_config.py` — `.codex/config.toml`, `observability/**/*.yml`에 절대경로·홈 경로 금지.
8. `test_no_direct_helpers.py` — `utils-*.js/py` 같은 ad-hoc 헬퍼 파일 이름 금지(공용 모듈에 머지).

## C. CI 실패 조건
- 위 항목 중 하나라도 실패 시 머지 차단.
- 위반 수는 `docs/generated/drift-report.md`에 주간 누적.

## D. pseudo-code 예시
```python
# tests/structure/test_layering.py
import importlib, pkgutil, networkx as nx
from tests.structure.helpers import build_import_graph, DIRECTION

def test_backend_layering():
    G = build_import_graph("backend/app")
    forbidden = [
        ("services", "routers"),
        ("services", "main"),
        ("core", "services"),
    ]
    for a, b in forbidden:
        assert not nx.has_path(G, a, b), f"{a} must not depend on {b}"
```

## E. 위반 사례 5개와 수정
1. `services/crawler_service.py`가 `fastapi.Request`를 import → 수정: router에서 필요한 값만 dict로 전달.
2. `components/chat/ChatPanel.jsx`에서 `fetch('/api/chat')` → 수정: `lib/apiClient.js`에 메서드 추가 후 그것을 호출.
3. 500줄짜리 `llm_service.py` → 수정: `llm/prompting.py`, `llm/parsing.py`로 분할.
4. `app/config.py` 외부 파일에 `MAX_TOKENS = 4096` 중복 → 수정: config로 이동 후 import.
5. `.codex/config.toml`에 `cwd = "C:\\..."` → 수정: `.codex/config.local.toml`로 이동, gitignore.
