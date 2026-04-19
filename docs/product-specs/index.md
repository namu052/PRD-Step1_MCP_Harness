# Product Specs Index

> **Source of truth**: *제품이 무엇을 하는가*의 진실은 여기. 기능을 추가/변경하려면 먼저 해당 spec 문서를 갱신한 뒤 exec-plan을 생성한다.

## 현재 스펙
| Slug | 제목 | 상태 |
|------|------|------|
| [overview](./overview.md) | 지방세 지식인 제품 개요 | active |

## 템플릿
```md
# <feature>

**Status**: draft | active | deprecated
**Owner**: <team/person>
**Last updated**: YYYY-MM-DD

## Goal
## Users & Jobs-to-be-done
## UX / Flows
## Functional requirements
## Non-functional requirements (perf, reliability, security)
## Data model summary
## Out of scope
## Open questions
## Linked
- design-docs/NN-<slug>
- exec-plans/active/<slug>
```

## 규칙
- 제품 스펙과 설계(`design-docs/`)는 분리한다. 여기에 “어떻게 구현할지”를 쓰지 않는다.
- 변경 시 `Last updated`를 반드시 갱신. 미갱신 문서는 신선도 점검 job이 경고.
