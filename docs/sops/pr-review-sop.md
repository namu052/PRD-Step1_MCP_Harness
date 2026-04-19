# SOP — PR 리뷰

리뷰 체계 상세는 `docs/policies/PR_REVIEW.md`를 따른다. 본 SOP는 실행 루틴을 요약한다.

## 리뷰 루틴
1. PR 본문/템플릿 채워짐 확인
2. `scripts/verify.sh` 결과(아티팩트) 확인
3. 구조 검사, UI 회귀, 품질 점수 확인
4. diff 읽기(≤ 400 LOC 권장)
5. 5~8개의 주 포인트 코멘트
6. 승인/수정요청/에스컬레이션

## 자동 리뷰어(선택)
- code-reviewer 서브에이전트를 1차 리뷰에 활용 가능. **승인은 사람**.

## 실패한 CI 처리
- 에이전트 1회 자동 재시도 허용. 재시도도 실패 시 사람 리뷰.
- “flaky”로 판단되면 `docs/exec-plans/tech-debt-tracker.md`에 등록 후 차단 해제.

## 머지
- Squash merge 기본.
- merge commit 메시지는 PR 제목 + plan 링크 포함.
