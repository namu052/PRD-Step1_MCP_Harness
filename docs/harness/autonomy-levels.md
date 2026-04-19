# 자율성 레벨 상세 매트릭스

세부 정의는 `docs/harness/execution-loop.md`의 Level 1/2/3 절을 참조한다. 본 문서는 *도구 설정 매핑*을 보관한다.

| 속성 | Level 1 Shadow | Level 2 Supervised | Level 3 Delegated (범위 명시) |
|------|----------------|---------------------|--------------------------------|
| 코드 수정 | ❌ | ✅ (feature scope) | ✅ (화이트리스트) |
| 테스트/스크립트 추가 | ❌ | ✅ | ✅ |
| 정책·CI·보안 수정 | ❌ | ❌ | ❌ |
| 스키마/마이그레이션 | ❌ | ❌ | ❌ |
| 외부 API 쓰기 호출 | ❌ | 승인 시 | 승인 시 |
| PR 생성 | draft | 정식 | 정식 (자동 머지는 cleanup만) |
| Codex 설정 | `approval = untrusted`, `sandbox = read-only` | `approval = on-request`, `sandbox = workspace-write` | `approval = on-failure`, worktree 강제 |
| Claude 설정 | Write/Edit/Bash 훅 차단 | Edit 허용, Bash 화이트리스트 | 스킬 고정 + hooks로 경로 제한 |
| 인간 승인 | 모든 PR | 머지 시점 | cleanup 제외 머지 시점 |

## 레벨 전환 규칙
- 승격: 2주 연속 실패 0건 + PR 품질 점수 평균 ≥ 0.9 (기준: `docs/policies/QUALITY_SCORE.md`).
- 강등: 단일 고위험 사고 or 2주 연속 실패 ≥ 2건 시 즉시 한 단계 강등.
- 모든 전환은 `docs/exec-plans/completed/`에 기록하고 PR에 링크한다.
