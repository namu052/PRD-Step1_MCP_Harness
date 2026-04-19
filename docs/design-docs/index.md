# Design Docs Index

> **Source of truth**: 본 저장소의 설계 결정은 이 디렉터리에만 기록한다. 코드 주석·PR 설명에 설계 근거를 흩뿌리지 않는다.

## 작성 규칙
- 파일명: `NN-<slug>.md` (NN은 연속 번호, slug는 kebab-case)
- 각 문서는 **Problem → Options → Decision → Consequences → Status**를 반드시 포함
- Status: `proposed`, `accepted`, `superseded-by:NN`, `deprecated`
- 변경이 생기면 **수정이 아니라 superseded 문서 추가**를 기본으로 한다

## 템플릿
```md
# NN — <title>

**Status**: proposed | accepted | superseded-by:NN | deprecated
**Date**: YYYY-MM-DD
**Owners**: <name or team>
**Related**: product-specs/<slug>, exec-plans/active/<slug>

## Problem
## Options
### Option A — <name>
pros / cons
### Option B — <name>
pros / cons
## Decision
## Consequences
- + positive
- − negative
- neutral
## Follow-ups
- links to exec-plans
```

## 신선도 관리
- 분기당 1회 Owner가 Status 확인. 90일 이상 `proposed` → 자동 `stale` 라벨.
- `scripts/check-docs-freshness.py`가 만료·고아(referenced 없음) 문서를 주간 보고.

## 현재 문서
| # | Title | Status | Owner |
|---|-------|--------|-------|
| 00 | [Quality × Latency Baseline](00-quality-latency-baseline.md) | accepted | backend lead |
| 01 | [Crawler Concurrency and Persistent Cache](01-crawler-concurrency-and-cache.md) | accepted | backend lead |
| 02 | [Hybrid Retrieval and Domain Priors](02-hybrid-retrieval-and-domain-priors.md) | accepted | backend lead |
| 03 | [Verification Tiers, Bidirectional Check, Multi-round Revision](03-verification-tiers-and-multiround.md) | accepted | backend + frontend lead |
| 04 | [Progressive SSE Event Contract](04-sse-progressive-events.md) | accepted | backend + frontend lead |
| 05 | [MCP Session Store Abstraction](05-mcp-session-store.md) | accepted | backend lead |
