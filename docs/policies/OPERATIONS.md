# OPERATIONS — 운영 정책 (섹션 15)

각 정책은 **정책명 / 필요성 / 규칙 / 자동화 / 위반 조치 / Codex / Claude** 순으로 정리한다.

## OP-1 보안
- 필요성: 시크릿 유출·무단 접근 방지
- 규칙: `docs/policies/SECURITY.md` 참조, 시크릿은 `.env`/CI secrets에만, 마스킹 필수
- 자동화: `scripts/lint-config.py`, 훅에서 secret 패턴 탐지
- 위반 조치: PR 차단, 즉시 키 회전, 사고 리포트
- Codex: MCP env_vars는 이름만
- Claude: PreToolUse 훅에서 secret 패턴 차단

## OP-2 비밀정보 처리
- 필요성: 에이전트 컨텍스트에 비밀이 남으면 로그 누수 위험
- 규칙: 원문 저장 금지, 처리 후 즉시 마스킹, 메모리/플랜에 넣지 않음
- 자동화: Hook/logger의 redactor
- 위반 조치: 해당 컨텍스트 폐기, 키 회전
- Codex: subagent 입력에 비밀 전달 금지
- Claude: memory에 kind가 `secret*`이면 저장 거부

## OP-3 프로덕션 변경 권한
- 필요성: 에이전트의 프로덕션 직결 사고 방지
- 규칙: 프로덕션 리소스 변경은 사람 승인 + 2인 검토 + 롤백 플랜
- 자동화: CD 파이프라인이 `requires-human-approval` gate
- 위반 조치: 즉시 롤백, 승인 로그 검토
- Codex: `approval_policy = "on-request"` 고정
- Claude: deploy 관련 tool 호출 시 hooks 차단

## OP-4 데이터 접근 통제
- 필요성: 개인정보/기밀 보호
- 규칙: 개발은 합성 데이터, 실데이터는 마스킹 뷰, 프로덕션 DB는 사람 세션
- 자동화: DB 연결 문자열이 prod일 때 훅 차단
- 위반 조치: 감사 로그로 추적, 즉시 세션 종료
- Codex: MCP DB 서버를 prod 인스턴스로 등록 금지
- Claude: 훅에서 `prod`, `production` 호스트 차단

## OP-5 위험 명령 실행 제한
- 필요성: 비가역 사고 방지
- 규칙: `rm -rf`, `--force`, `DROP`, 마이그레이션 `down` 사람 승인
- 자동화: 명령 패턴 매칭 훅, CI에서 스크립트 금지 파싱
- 위반 조치: 자동 중단, 승인 요청
- Codex: `allowed_commands` 화이트리스트
- Claude: PreToolUse Bash 훅

## OP-6 롤백 정책
- 필요성: 사고 복구 시간 최소화
- 규칙: 모든 릴리즈 PR은 롤백 절차 필수(SOP 링크)
- 자동화: PR 템플릿에 섹션 강제
- 위반 조치: 릴리즈 보류
- Codex/Claude: 릴리즈 PR 생성 시 SOP 자동 삽입

## OP-7 장애 에스컬레이션
- 필요성: 책임 소재 명확화
- 규칙: 심각도별 에스컬레이션 경로, postmortem 필수
- 자동화: 알람 → on-call 페이징, 티켓 자동 생성
- 위반 조치: 사후 프로세스 검토
- Codex/Claude: 진단 보고서 자동 초안 생성

## OP-8 문서 신선도
- 필요성: 에이전트가 오래된 정보로 학습/행동하지 않게
- 규칙: 90일 이상 미갱신 + 관련 코드 변경 감지 시 드리프트
- 자동화: `scripts/check-docs-freshness.py`
- 위반 조치: 드리프트 PR 자동 제안

## OP-9 감사 로그
- 필요성: 에이전트 행동 추적
- 규칙: 모든 Bash/Edit/Write/승인 요청은 `observability/agent-actions/`에 기록
- 자동화: 훅에서 append-only 로깅
- 위반 조치: 로그 누락 탐지 시 Level 강등

## OP-10 인간 승인 게이트
- 필요성: 고위험 변경의 최종 판단
- 규칙: `docs/sops/human-approval-sop.md` 경로로만 승인 수집
- 자동화: PR 라벨 `needs-human-approval` 체크
- 위반 조치: 머지 차단
