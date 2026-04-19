# [섹션 17] 실패 패턴과 대응책 15선

| # | 패턴 | 징후 | 원인 | 조기 탐지 | 교정 |
|---|------|------|------|-----------|------|
| 1 | AGENTS.md/CLAUDE.md 중복 비대화 | 두 파일이 각각 200줄+, 같은 문단 다수 | 편의상 정책 본문을 허브에 넣음 | `scripts/check-docs-freshness.py` 줄 수·중복 섹션 규칙 | 장문을 `docs/policies/`로 이동, 허브는 링크만 |
| 2 | 문서 드리프트 | design-docs와 코드가 다름 | 변경 시 문서 동기화 누락 | 주간 drift-scan, 문서 mtime vs 관련 코드 mtime 비교 | 드리프트 PR 자동 생성, 사람 리뷰 |
| 3 | Source of truth 혼란 | 동일 규칙이 docs/policies, CLAUDE.md, 스크립트 주석에 다르게 | 계층 미합의 | `core-principles.md` 계층, 에이전트 체크리스트 | 하나만 남기고 다른 곳은 링크로 교체 |
| 4 | Codex config 난립 | config.toml이 사용자별로 다르게 커밋됨 | 공용/로컬 분리 규칙 부재 | `scripts/lint-config.py`로 금지 키(`cwd`, 절대경로) 체크 | `.codex/config.local.toml` 분리, 공용에는 화이트리스트 키만 |
| 5 | Claude skills 난립 | 스킬 20개 이상, 중복 목적 | 즉흥 생성 | 월간 스킬 감사, 실행 빈도 0회 경고 | 통합/삭제, 4~8개 유지 권장 |
| 6 | Hook 과잉 | 훅이 모든 명령을 가로채 속도·UX 저하 | 방어적 과적합 | 훅 실행 시간 로깅, 총 지연 예산 초과 경보 | 훅은 *차단*과 *자동 포맷* 위주로, 복잡 로직은 `scripts/`로 |
| 7 | 승인 정책 부적절 | 사소한 작업에도 승인 요청 남발 or 고위험이 무승인 | 작업 분류 부재 | PR 라벨 기반 분류, 승인율 지표 | Level 1/2/3 모델 적용, 경로별 화이트리스트 |
| 8 | 샌드박스 과개방/과제한 | 과개방: 의도하지 않은 파일 쓰기. 과제한: 매번 승인 요청 | 단일 모드 고정 | 작업 유형별 샌드박스 설정 강제 | `docs/sops/codex-sop.md`의 프로파일 표 |
| 9 | 구조 제약 미강제 | 레이어 위반이 PR에 섞여 머지 | 규칙이 문서에만 존재 | `tests/structure/` CI 실패로 차단 | 위반을 PR 차단 조건으로 |
| 10 | 테스트 통과, UI 깨짐 | 유닛은 녹색, 실제 동작 실패 | E2E/UI 부재 | Playwright 10 시나리오 필수 | UI regression을 merge gate에 포함 |
| 11 | 로그 있으나 해석 불가 | 원시 텍스트, 필드 비표준 | JSON 비적용, 공통 키 부재 | 로그 스키마 lint | `docs/harness/observability.md` 스키마로 교체 |
| 12 | PR 과대화 | 한 PR이 ≥ 1000 LOC, 무관 변경 혼재 | plan 없는 즉흥 작업 | PR 사이즈 체크 CI | 400 LOC 상한, 초과 시 자동 comment |
| 13 | 임시 패치 누적 | `TODO:` / `# XXX:` 증가 | tech-debt tracker 미사용 | 주간 스캔, 임계치 경보 | `docs/exec-plans/tech-debt-tracker.md`에 항목 등록 필수 |
| 14 | 승인 기준 불명확 | 누가 언제 승인하는지 사람마다 다름 | SOP 미비 | 승인 로그 감사 | `docs/sops/human-approval-sop.md` 일원화 |
| 15 | 잘못된 로컬 패턴 학습 | 에이전트가 구식 컨벤션 재생산 | 과거 문서 미정리 | `docs/references/`의 *legacy* 표시 관행 | 오래된 문서 `archived/` 이동, 에이전트 체크리스트에서 배제 |
