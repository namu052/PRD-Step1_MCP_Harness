# RELIABILITY — 신뢰성 정책

## 가용성 목표
- Dev: best-effort, 재현 가능한 실패 우선.
- Staging: 영업일 99%.
- Prod(해당 시): 영업일 99.5%, 핵심 플로우 p95 latency ≤ 3s.

## 에러 예산 & 롤백
- 단일 릴리즈가 에러 예산의 50% 이상 소모 시 즉시 롤백.
- 롤백 절차는 `docs/sops/human-approval-sop.md#rollback`에 단일화.

## 테스트 피라미드
| 계층 | 목표 커버리지 | 실행 주기 |
|------|---------------|-----------|
| unit | 80%+ | 매 PR |
| integration | 핵심 경로 100% | 매 PR |
| E2E UI | 시나리오 10개 | 매 PR(필수), nightly 확대 |
| 구조 검사 | 규칙 수 == 검사 수 | 매 PR |

## 장애 대응
1. 감지(알람/리포트) → 2. 트리아지(심각도 판정) → 3. 완화(롤백·차단) → 4. 근본 원인 → 5. postmortem → 6. tech-debt 등록.
- postmortem은 `docs/design-docs/`에 `Status: accepted`로 저장.

## 데이터 무결성
- 이중 쓰기 전환 시 dual-write → shadow read → cutover.
- 마이그레이션은 `expand → migrate → contract` 3단계 PR.

## Codex 추가
- 장시간 작업은 subagent + timeout 설정. `tool_timeout_sec` 상한 공용 policy로 관리.

## Claude 추가
- `run-verification` 스킬이 실패 시 자동 재시도 ≤ 2회, 이후 사람 에스컬레이션.
