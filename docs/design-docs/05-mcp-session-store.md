# 05 — MCP Session Store Abstraction

**Status**: accepted
**Date**: 2026-04-17
**Owners**: backend lead
**Related**: product-specs/overview, exec-plans/active/backend-step8-mcp-modularization-progressive-sse, design-docs/01-crawler-concurrency-and-cache

## Problem
`backend/mcp_server.py`의 `_MCPSession`(57~115)은 `dict` + 타임스탬프로 TTL 5분 캐시를 수동 관리한다. 프로세스 재시작 시 즉시 소실되고, 멀티워커 환경에 이식 불가. 또한 Plan 1의 SQLite 영속 캐시(`crawl_cache.db`)와 **스키마·TTL 철학이 분리**되어 있어 캐시 계층이 2개로 난립할 수 있다.

## Options
### Option A — 전면 Redis 도입
pros: 표준, 멀티워커 자연스러움
cons: 외부 인프라 의존, 로컬 개발/테스트 부담, 2주 범위 초과

### Option B — `SessionStore` 프로토콜 + `InMemoryStore` / `SqliteStore` 두 구현
pros: 인터페이스만 정의, 의존성 0 유지, Plan 1 SQLite와 파일 공유 가능
cons: Redis 전환 시 한 층 더 필요

### Option C — 현재 dict 유지, 분할만
pros: 저위험
cons: 재시작/멀티워커 문제 미해결

## Decision
**Option B**. 공용 프로토콜 정의 + in-memory가 기본, SQLite는 opt-in. Plan 1의 `crawl_cache.db`와 **동일 SQLite 파일**을 `namespace` 컬럼으로 공유(크롤 결과 vs 세션 캐시).

### 프로토콜
```python
class SessionStore(Protocol):
    def get(self, namespace: str, key: str) -> Any | None: ...
    def set(self, namespace: str, key: str, value: Any, ttl: int) -> None: ...
    def delete(self, namespace: str, key: str) -> None: ...
    def prune_expired(self) -> int: ...   # 주기적 호출
```

### 구현
- `InMemoryStore`: 기존 `_MCPSession` 동작 이식. 단위 테스트로 legacy 동작 동일성 보증
- `SqliteStore`: `namespace TEXT, key TEXT, payload BLOB, expires_at INTEGER, PRIMARY KEY(namespace, key)`, WAL 모드, 쓰기 락 경합 완화
- 선택 스위치: env `SESSION_STORE=memory|sqlite` (기본 memory)

### 네임스페이스 사용 예
```
crawl         : Plan 1 영속 캐시
ranked        : 임베딩 랭킹 결과 (기존 in-memory)
evidence_slots: 근거 묶음
search_plan   : Plan 2 SearchPlan 캐시
```

### TTL 정책 (일원화)
| 네임스페이스 | TTL | 근거 |
|-------------|-----|------|
| crawl       | 3600s (1h) | OLTA 콘텐츠 갱신 주기 보수적 추정 |
| ranked      | 300s       | 임베딩 랭킹은 같은 crawl 기반이므로 짧게 |
| evidence_slots | 300s   | ranked와 수명 동기 |
| search_plan | 86400s (24h) | 질문 정규화되어 안정적 |

## Consequences
- **+** 멀티워커/재시작 환경에서도 캐시 생존(Sqlite 선택 시)
- **+** 캐시 저장소가 하나로 집중(TD-0001 해소 과정에 자연 편입)
- **+** Redis 전환 시 `RedisStore`만 추가하면 됨
- **−** SQLite 쓰기 락 — WAL + 배치 쓰기로 완화. 부하 증가 시 디커플링(별도 프로세스) 재검토
- neutral: 프로토콜은 동기. async 어댑터가 필요해지면 `AsyncSessionStore`로 상속

## Follow-ups
- `exec-plans/active/backend-step8-mcp-modularization-progressive-sse.md`
- Redis 전환 trigger: 운영 워커 수 ≥ 2 또는 P95 캐시 락 대기 > 50ms
