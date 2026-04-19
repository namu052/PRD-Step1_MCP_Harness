"""MCP Server for 지방세 질의응답 (Local Tax Q&A).

Claude Code에서 OLTA 크롤링 + LLM 답변 생성 파이프라인을
MCP tool로 사용할 수 있도록 노출한다.

실행: python mcp_server.py  (stdio transport)
테스트: mcp dev mcp_server.py  (inspector UI)
"""

import asyncio
import atexit
import logging
import logging.handlers
import os
import re
import sys
import time
import warnings

# ── Windows Playwright 호환 이벤트 루프 ──
if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ── 로깅: stderr + 파일 동시 출력 ──
_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "mcp_server.log")

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(_formatter)

_file_handler = logging.handlers.RotatingFileHandler(
    _log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
_file_handler.setFormatter(_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_stderr_handler, _file_handler],
)
logger = logging.getLogger("mcp_server")
logger.info("MCP 서버 로그 파일: %s", _log_file)

from mcp.server.fastmcp import FastMCP  # noqa: E402

# ── FastMCP 인스턴스 ──
mcp = FastMCP("지방세-질의응답")

# ── 동시성 보호: Playwright 공유 페이지가 하나이므로 크롤링 직렬화 ──
_crawl_lock = asyncio.Lock()


# ── 세션 + 캐싱 (모듈 싱글톤) ──
class _MCPSession:
    CACHE_TTL = 300.0  # 5분

    def __init__(self):
        self.crawl_cache: dict = {}
        # 질문별 결과 캐시
        self._crawl_results: dict[str, list] = {}
        self._ranked_results: dict[str, list] = {}
        self._evidence_slots: dict[str, list] = {}
        self._timestamps: dict[str, float] = {}

    def _is_valid(self, key: str) -> bool:
        ts = self._timestamps.get(key, 0.0)
        return (time.time() - ts) < self.CACHE_TTL

    def get_crawl(self, question: str):
        if question in self._crawl_results and self._is_valid(question):
            return self._crawl_results[question]
        return None

    def get_ranked(self, question: str):
        if question in self._ranked_results and self._is_valid(question):
            return self._ranked_results[question]
        return None

    def get_evidence(self, question: str):
        if question in self._evidence_slots and self._is_valid(question):
            return self._evidence_slots[question]
        return None

    def set_crawl(self, question: str, results: list):
        self._crawl_results[question] = results
        self._timestamps[question] = time.time()

    def set_ranked(self, question: str, results: list):
        self._ranked_results[question] = results
        self._timestamps[question] = time.time()

    def set_evidence(self, question: str, slots: list):
        self._evidence_slots[question] = slots
        self._timestamps[question] = time.time()

    def find_by_source_id(self, source_id: str):
        """캐시된 모든 ranked 결과에서 source_id로 검색."""
        for results in self._ranked_results.values():
            for r in results:
                if r.id == source_id:
                    return r
        return None

    def clear(self):
        self._crawl_results.clear()
        self._ranked_results.clear()
        self._evidence_slots.clear()
        self._timestamps.clear()


_session = _MCPSession()


# ═══════════════════════════════════════════
# Tool 1: OLTA 로그인 상태 확인
# ═══════════════════════════════════════════
@mcp.tool()
async def check_olta_login() -> str:
    """OLTA(지방세법령포털) 로그인 상태를 확인합니다.

    로그인 상태에 따라 수집 가능한 자료 범위가 달라집니다.
    - 로그인됨: 법령, 판례, 유권해석, BBS 게시판 전체 수집 가능
    - 미로그인: 법령, 판례 등 기본 자료만 수집 가능 (BBS 제외)
    """
    try:
        from app.services.crawler_service import crawler_service

        logged_in = await crawler_service.check_olta_login()
        if logged_in:
            return "OLTA 로그인 상태: ✅ 로그인됨 — 전체 자료(BBS 포함) 수집 가능"
        return (
            "OLTA 로그인 상태: ❌ 미로그인 — BBS 게시판 수집 불가.\n"
            "'open_olta_for_login' 도구를 사용하여 Playwright 브라우저에서 수동 로그인해 주세요."
        )
    except Exception as exc:
        logger.error("check_olta_login 실패", exc_info=True)
        return f"OLTA 상태 확인 실패: {exc}"


# ═══════════════════════════════════════════
# Tool 2: OLTA 로그인용 브라우저 열기
# ═══════════════════════════════════════════
@mcp.tool()
async def open_olta_for_login() -> str:
    """OLTA 로그인을 위해 Playwright 브라우저를 엽니다.

    브라우저 창에서 직접 OLTA에 로그인한 후,
    'check_olta_login' 도구로 로그인 상태를 확인하세요.
    로그인 상태는 공유 프로파일에 저장되어 서버 재시작 후에도 유지됩니다.
    """
    try:
        from app.services.crawler_service import crawler_service

        url = await crawler_service.open_olta_for_login()
        return (
            f"Playwright 브라우저에서 OLTA 로그인 페이지를 열었습니다.\n"
            f"URL: {url}\n\n"
            f"브라우저 창에서 수동으로 로그인해 주세요.\n"
            f"로그인 완료 후 'check_olta_login'으로 확인할 수 있습니다."
        )
    except Exception as exc:
        logger.error("open_olta_for_login 실패", exc_info=True)
        return f"OLTA 브라우저 열기 실패: {exc}"


# ═══════════════════════════════════════════
# Tool 3: OLTA 브라우저 종료
# ═══════════════════════════════════════════
@mcp.tool()
async def close_olta_browser() -> str:
    """Playwright 브라우저를 종료하고 자원을 정리합니다."""
    try:
        from app.services.crawler_service import crawler_service

        await crawler_service.close_browser()
        return "OLTA 브라우저가 종료되었습니다."
    except Exception as exc:
        logger.error("close_olta_browser 실패", exc_info=True)
        return f"브라우저 종료 실패: {exc}"


# ═══════════════════════════════════════════
# Tool 4: 질문 분석 미리보기 (크롤링 없음)
# ═══════════════════════════════════════════
@mcp.tool()
async def get_search_plan(question: str) -> str:
    """질문을 분석하여 검색 계획을 미리 보여줍니다 (크롤링 없음).

    OLTA 크롤링 없이 LLM으로 질문 유형, 세목, 쟁점, 검색어 조합, BBS 우선순위 등을 분석합니다.
    search_olta나 ask_local_tax 실행 전에 검색 전략을 확인할 때 유용합니다.
    소요 시간: 약 3-5초
    """
    try:
        from app.services.search_service import search_service

        plan = await search_service.build_search_plan(question)

        lines = [
            "## 검색 계획 분석",
            f"- 질문 유형: {plan.question_type}",
            f"- 주요 세목: {plan.primary_tax_type or '미지정'}",
            f"- 주요 쟁점: {plan.primary_topic or '미지정'}",
            f"- 연도 기준: {plan.weighting_label}",
            f"- 감지 연도: {plan.detected_year or '없음'}",
            "",
            "### 검색어 조합 (OLTA에 입력할 쿼리)",
        ]
        for i, q in enumerate(plan.search_queries, 1):
            lines.append(f'  {i}. "{q}"')

        lines.append("")
        lines.append("### 수집 카테고리")
        category_labels = {
            "law_search": "법령",
            "interpret_search": "유권해석",
            "case_search": "판례/결정례",
        }
        for cat in plan.categories:
            lines.append(f"  - {category_labels.get(cat, cat)}")

        lines.append("")
        lines.append("### BBS 우선 게시판")
        for board in plan.priority_bbs_boards[:5]:
            lines.append(f"  - {board}")

        if plan.keywords:
            lines.append("")
            lines.append("### 추출 키워드")
            lines.append(f"  {', '.join(plan.keywords)}")

        if plan.analysis_focus:
            lines.append("")
            lines.append("### 분석 방향")
            for af in plan.analysis_focus:
                lines.append(f"  - {af}")

        if plan.collection_focus:
            lines.append("")
            lines.append("### 수집 우선순위")
            for cf in plan.collection_focus:
                lines.append(f"  - {cf}")

        return "\n".join(lines)
    except Exception as exc:
        logger.error("get_search_plan 실패", exc_info=True)
        return f"검색 계획 분석 실패: {exc}"


# ═══════════════════════════════════════════
# Tool 5: 브라우저에 HTML 답변 표시
# ═══════════════════════════════════════════
@mcp.tool()
async def show_answer_in_browser(html_content: str) -> str:
    """Playwright 브라우저에 새 탭을 열어 HTML 콘텐츠를 표시합니다.

    답변이나 분석 결과를 HTML 형식으로 렌더링하여 시각적으로 보여줄 때 사용하세요.
    마크다운을 HTML로 변환한 후 이 도구로 전달하면 보기 좋은 팝업이 열립니다.
    """
    try:
        from app.services.crawler_service import crawler_service

        result = await crawler_service.show_answer_popup(html_content)
        return f"브라우저 팝업이 열렸습니다. {result}"
    except Exception as exc:
        logger.error("show_answer_in_browser 실패", exc_info=True)
        return f"팝업 표시 실패: {exc}"


# ═══════════════════════════════════════════
# Tool 6: 캐시된 문서 상세 조회
# ═══════════════════════════════════════════
@mcp.tool()
async def get_document_content(source_id: str) -> str:
    """캐시된 검색 결과에서 특정 문서의 전체 내용을 조회합니다.

    search_olta나 ask_local_tax 실행 후, 결과 목록의 source_id를 지정하면
    해당 문서의 전체 본문(content)을 반환합니다.
    먼저 search_olta 또는 ask_local_tax를 실행하여 결과를 캐시해야 합니다.
    """
    result = _session.find_by_source_id(source_id)
    if not result:
        return (
            f"'{source_id}'를 캐시에서 찾을 수 없습니다.\n"
            "search_olta 또는 ask_local_tax를 먼저 실행하여 결과를 캐시한 후 다시 시도해 주세요."
        )

    lines = [
        f"## [{result.id}] {result.title}",
        f"- 유형: {result.type}",
        f"- 연도: {result.document_year or '미상'}",
        f"- 관련도: {result.relevance_score:.2f}" if result.relevance_score else "",
    ]
    if result.url:
        lines.append(f"- URL: {result.url}")
    if hasattr(result, "source_query") and result.source_query:
        lines.append(f"- 수집 검색어: {result.source_query}")

    lines.append("")
    lines.append("### 본문")
    lines.append(result.content if result.content else "(본문 없음)")

    if hasattr(result, "comments") and result.comments:
        lines.append("")
        lines.append("### 코멘트")
        lines.append(result.comments)

    return "\n".join(lines)


# ═══════════════════════════════════════════
# Tool 7: 캐시 초기화
# ═══════════════════════════════════════════
@mcp.tool()
async def clear_cache() -> str:
    """MCP 서버의 검색 결과 캐시를 초기화합니다.

    캐시된 크롤링 결과, 랭킹 결과, 근거 묶음을 모두 삭제합니다.
    새로운 검색을 위해 이전 결과를 무효화하고 싶을 때 사용하세요.
    """
    _session.clear()
    return "캐시가 초기화되었습니다. 다음 검색 시 OLTA에서 새로 수집합니다."


# ═══════════════════════════════════════════
# 공통: OLTA 로그인 게이트
# ═══════════════════════════════════════════
async def _ensure_olta_login() -> str | None:
    """OLTA 로그인 상태를 확인하고, 미로그인 시 브라우저를 열어 안내한다."""
    from app.services.crawler_service import crawler_service

    # ── 1) 이미 로그인되어 있는지 확인 ──
    logger.info("▶ _ensure_olta_login: 로그인 확인 시작")
    try:
        logged_in = await crawler_service.check_olta_login()
    except Exception:
        logged_in = False

    logger.info("▶ _ensure_olta_login: logged_in=%s", logged_in)
    if logged_in:
        return None

    # ── 2) 미로그인 → 브라우저 열고 안내 후 중단 ──
    try:
        url = await crawler_service.open_olta_for_login()
        logger.info("OLTA 미로그인 — 브라우저 열림, 사용자 로그인 대기")
        return (
            "❌ OLTA 미로그인 상태입니다.\n\n"
            f"Playwright 브라우저에서 OLTA 로그인 페이지를 열었습니다.\n"
            f"URL: {url}\n\n"
            "브라우저 창에서 로그인을 완료한 후, '로그인 했다'고 알려주세요.\n"
            "그러면 자동으로 자료 수집을 시작합니다."
        )
    except Exception as exc:
        logger.error("OLTA 로그인 브라우저 열기 실패", exc_info=True)
        return (
            "❌ OLTA 미로그인 상태이며, 브라우저 열기도 실패했습니다.\n"
            f"오류: {exc}\n\n"
            "'open_olta_for_login' 도구로 수동으로 시도해 주세요."
        )


# ═══════════════════════════════════════════
# Tool 8: OLTA 검색 (LLM 답변 없이 자료만 수집)
# ═══════════════════════════════════════════
@mcp.tool()
async def search_olta(
    question: str,
    custom_queries: list[str] | None = None,
    categories: list[str] | None = None,
    priority_boards: list[str] | None = None,
) -> str:
    """OLTA에서 지방세 관련 자료를 검색하고 랭킹된 결과를 반환합니다.

    LLM 답변은 생성하지 않으며, 수집된 자료 목록만 제공합니다.
    Claude가 직접 자료를 분석하고 싶을 때 사용하세요.
    결과는 캐시되어 get_document_content로 상세 조회할 수 있습니다.
    소요 시간: 약 15-30초 (캐시 히트 시 즉시)

    Args:
        question: 지방세 관련 질문
        custom_queries: 사용자 지정 OLTA 검색어 목록 (미지정 시 LLM이 자동 생성)
        categories: 수집 카테고리 필터 (law_search, interpret_search, case_search)
        priority_boards: BBS 우선 탐색 게시판 목록 (예: ["질의응답", "지방세상담"])
    """
    async with _crawl_lock:
        try:
            return await asyncio.wait_for(
                _run_search_pipeline(question, custom_queries, categories, priority_boards),
                timeout=360,
            )
        except asyncio.TimeoutError:
            logger.error("search_olta 전체 파이프라인 타임아웃(360s)")
            return "검색 실패: 파이프라인이 6분을 초과했습니다. OLTA 접속 상태를 확인해 주세요."
        except Exception as exc:
            logger.error("search_olta 실패", exc_info=True)
            return f"검색 실패: {exc}"


async def _crawl_with_retries(
    question: str,
    search_plan,
    crawler_service,
    search_service,
    label: str = "search",
) -> list:
    """공통 크롤링 로직: 1차 → fallback 키워드(2-B) → 질문 축약(2-C).

    - fallback 재시도(2-B, 2-C)는 BBS 탐색을 건너뛰고 타임아웃을 건다.
    - 브라우저/네트워크 수준 실패 시 연쇄 재시도하지 않고 즉시 빈 결과 반환.
    """
    # ── 1차 크롤링 ──
    logger.info("[%s] Stage 2: OLTA 크롤링 시작", label)
    try:
        crawl_results = await asyncio.wait_for(
            crawler_service.search(
                _session, search_plan.search_queries, search_plan.categories,
            ),
            timeout=300,
        )
    except asyncio.TimeoutError:
        logger.warning("[%s] Stage 2: 1차 크롤링 타임아웃(300s) — 재시도 없이 중단", label)
        return []

    # ── 2-B: 0건 시 fallback 키워드 재시도 (BBS 없이, 타임아웃 90s) ──
    if not crawl_results and search_plan.keywords:
        logger.info("[%s] Stage 2-B: 1차 검색 0건 — fallback 키워드로 재시도", label)
        fallback_queries = search_service._build_fallback_queries(question, search_plan.keywords)
        if fallback_queries and fallback_queries != search_plan.search_queries:
            try:
                crawl_results = await asyncio.wait_for(
                    crawler_service.search(
                        _session, fallback_queries, search_plan.categories,
                        skip_bbs=True,
                    ),
                    timeout=90,
                )
            except asyncio.TimeoutError:
                logger.warning("[%s] Stage 2-B: fallback 크롤링 타임아웃(90s)", label)
                crawl_results = []
            if crawl_results:
                search_plan.search_queries = fallback_queries

    # ── 2-C: 3차 재시도 — 질문 원문 축약 (BBS 없이, 타임아웃 60s) ──
    if not crawl_results:
        compact = re.sub(r"[?.,()에서을를이가의은는도에게로부터]", " ", question)
        compact = re.sub(r"\s+", " ", compact).strip()[:30]
        if compact:
            logger.info("[%s] Stage 2-C: 질문 축약으로 재시도: '%s'", label, compact)
            try:
                crawl_results = await asyncio.wait_for(
                    crawler_service.search(
                        _session, [compact], search_plan.categories,
                        skip_bbs=True,
                    ),
                    timeout=60,
                )
            except asyncio.TimeoutError:
                logger.warning("[%s] Stage 2-C: 축약 크롤링 타임아웃(60s)", label)
                crawl_results = []

    return crawl_results


_CRAWL_EMPTY_MSG = (
    "OLTA에서 자료를 수집하지 못했습니다.\n"
    "OLTA 접속 상태를 확인해 주세요.\n"
    "'check_olta_login' 도구로 상태를 확인할 수 있습니다."
)


async def _run_search_pipeline(
    question: str,
    custom_queries: list[str] | None = None,
    categories_override: list[str] | None = None,
    priority_boards_override: list[str] | None = None,
) -> str:
    from app.config import get_settings
    from app.services.crawler_service import crawler_service
    from app.services.embedding_service import embedding_service
    from app.services.search_service import search_service

    settings = get_settings()

    # 캐시 확인 (커스텀 파라미터 없을 때만)
    if not custom_queries and not categories_override and not priority_boards_override:
        cached_ranked = _session.get_ranked(question)
        if cached_ranked is not None:
            logger.info("[search] 캐시 히트: %d건", len(cached_ranked))
            return _format_search_results(question, cached_ranked, "(캐시된 결과)")

    # 0) OLTA 로그인 필수 확인
    login_block = await _ensure_olta_login()
    if login_block:
        return login_block

    # 1) 검색 계획
    logger.info("[search] Stage 1: 검색 계획 생성 시작")
    search_plan = await search_service.build_search_plan(question)

    # 커스텀 파라미터 오버라이드
    if custom_queries:
        search_plan.search_queries = custom_queries
    if categories_override:
        search_plan.categories = categories_override
    if priority_boards_override:
        search_plan.priority_bbs_boards = priority_boards_override

    logger.info(
        "[search] Stage 1 완료: type=%s queries=%s bbs=%s",
        search_plan.question_type,
        search_plan.search_queries,
        search_plan.priority_bbs_boards[:3],
    )

    # 2) OLTA 크롤링 (공통 재시도 로직)
    crawl_results = await _crawl_with_retries(
        question, search_plan, crawler_service, search_service, label="search",
    )

    if not crawl_results:
        return _CRAWL_EMPTY_MSG

    # 캐시 저장
    _session.set_crawl(question, crawl_results)

    # ── 크롤링 완료 → OLTA JS 타이머 중단 (이벤트 루프 해방) ──
    await crawler_service.quiet_page()

    # 3) 임베딩 랭킹
    ranked = await embedding_service.rank_results(
        question,
        crawl_results,
        preferred_year=search_plan.detected_year,
        prefer_latest=search_plan.prefer_latest,
        search_queries=search_plan.search_queries,
    )

    # 3-B) 관련도 하한 필터
    if len(ranked) > 5:
        min_score = ranked[0].relevance_score * settings.min_relevance_ratio
        filtered = [r for r in ranked if r.relevance_score >= min_score]
        ranked = filtered if len(filtered) >= 5 else ranked[:max(5, len(filtered))]

    # 캐시 저장
    _session.set_ranked(question, ranked)

    return _format_search_results(question, ranked, search_plan=search_plan, total_crawled=len(crawl_results))


def _format_search_results(
    question: str,
    ranked: list,
    cache_note: str = "",
    search_plan=None,
    total_crawled: int = 0,
) -> str:
    """search_olta 결과를 마크다운으로 포매팅."""
    lines = []

    if cache_note:
        lines.append(f"*{cache_note}*\n")

    if search_plan:
        lines.extend([
            "## 검색 분석",
            f"- 질문 유형: {search_plan.question_type}",
            f"- 주요 세목: {search_plan.primary_tax_type or '미지정'}",
            f"- 주요 쟁점: {search_plan.primary_topic or '미지정'}",
            "- 검색어 조합:",
        ])
        for i, q in enumerate(search_plan.search_queries, 1):
            lines.append(f'  {i}. "{q}"')
        lines.extend([
            f"- 우선 BBS 게시판: {', '.join(search_plan.priority_bbs_boards[:3]) or '기본'}",
            f"- 수집 범위: {', '.join(search_plan.collection_focus) or '전체'}",
            f"- 연도 기준: {search_plan.weighting_label}",
            "",
        ])

    crawl_label = f"{total_crawled}건 수집 → " if total_crawled else ""
    lines.append(f"## 수집 결과: {crawl_label}{len(ranked)}건 랭킹\n")

    for i, r in enumerate(ranked, 1):
        year = f" ({r.document_year})" if r.document_year else ""
        score = f" [관련도: {r.relevance_score:.2f}]" if r.relevance_score else ""
        lines.append(f"{i}. **[{r.id}]** {r.title}{year} — {r.type}{score}")
        if r.preview:
            preview = r.preview[:200].replace("\n", " ")
            lines.append(f"   > {preview}")
        if r.url:
            lines.append(f"   URL: {r.url}")
        lines.append("")

    # 검색어별 수집 기여도
    query_counts: dict[str, int] = {}
    for r in ranked:
        sq = r.source_query or "미분류"
        query_counts[sq] = query_counts.get(sq, 0) + 1
    if any(sq != "미분류" for sq in query_counts):
        lines.append("## 검색어별 수집 기여도")
        for sq, count in sorted(query_counts.items(), key=lambda x: -x[1]):
            lines.append(f'  - "{sq}": {count}건')

    return "\n".join(lines)


# ═══════════════════════════════════════════
# Tool 9: 지방세 질의응답 (전체 파이프라인)
# ═══════════════════════════════════════════
@mcp.tool()
async def ask_local_tax(
    question: str,
    custom_queries: list[str] | None = None,
    categories: list[str] | None = None,
    priority_boards: list[str] | None = None,
    skip_verification: bool = True,
) -> str:
    """지방세 관련 질문에 대해 OLTA 자료를 검색하고 LLM 기반 답변을 생성합니다.

    전체 파이프라인을 실행합니다:
    1. 질문 분석 및 검색어 조합 생성 (3~4개)
    2. OLTA(지방세법령포털) 크롤링 + BBS 서브게시판 탐색
    3. 시맨틱 랭킹 및 근거 그루핑
    4. GPT-4o 기반 답변 생성 (출처 인용 포함)
    5. 답변 검증 (skip_verification=False 시 출처/내용/근거 교차 검증 + 자동 수정)

    소요 시간: 약 180-250초 (skip_verification=False 시 +30-60초 추가)

    Args:
        question: 지방세 관련 질문
        custom_queries: 사용자 지정 OLTA 검색어 목록 (미지정 시 LLM이 자동 생성)
        categories: 수집 카테고리 필터 (law_search, interpret_search, case_search)
        priority_boards: BBS 우선 탐색 게시판 목록 (예: ["질의응답", "지방세상담"])
        skip_verification: True면 답변 검증 단계를 건너뜁니다 (속도 우선)
    """
    async with _crawl_lock:
        try:
            return await asyncio.wait_for(
                _run_full_pipeline(
                    question, custom_queries, categories,
                    priority_boards, skip_verification,
                ),
                timeout=480,  # 검증 포함 8분 제한
            )
        except asyncio.TimeoutError:
            logger.error("ask_local_tax 전체 파이프라인 타임아웃(480s)")
            return "답변 생성 실패: 전체 파이프라인이 8분을 초과했습니다. OLTA 접속 상태를 확인해 주세요."
        except Exception as exc:
            logger.error("ask_local_tax 실패", exc_info=True)
            return f"답변 생성 실패: {exc}"


async def _run_full_pipeline(
    question: str,
    custom_queries: list[str] | None = None,
    categories_override: list[str] | None = None,
    priority_boards_override: list[str] | None = None,
    skip_verification: bool = False,
    *,
    golden_set_id: str | None = None,
) -> str:
    from app.config import get_settings
    from app.observability import new_req_id, quality_metric, stage_timed
    from app.services.crawler_service import crawler_service
    from app.services.embedding_service import embedding_service
    from app.services.evidence_group_service import evidence_group_service
    from app.services.evidence_summary_service import evidence_summary_service
    from app.services.llm_service import llm_service
    from app.services.search_service import search_service

    settings = get_settings()
    req_id = new_req_id()

    # ── OLTA 로그인 필수 확인 ──
    login_block = await _ensure_olta_login()
    if login_block:
        return login_block

    # ── Stage 1: 검색 계획 (search_queries 포함) ──
    logger.info("[pipeline] Stage 1: 검색 계획 생성 시작 req_id=%s", req_id)
    async with stage_timed("search_planning", req_id=req_id):
        search_plan = await search_service.build_search_plan(question)

    # 커스텀 파라미터 오버라이드
    if custom_queries:
        search_plan.search_queries = custom_queries
    if categories_override:
        search_plan.categories = categories_override
    if priority_boards_override:
        search_plan.priority_bbs_boards = priority_boards_override

    logger.info(
        "[pipeline] Stage 1 완료: type=%s queries=%s tax=%s topic=%s bbs=%s",
        search_plan.question_type,
        search_plan.search_queries,
        search_plan.primary_tax_type,
        search_plan.primary_topic,
        search_plan.priority_bbs_boards[:3],
    )

    # ── Stage 2: OLTA 크롤링 (캐시 확인 → 공통 재시도 로직) ──
    async with stage_timed("crawling", req_id=req_id) as t_crawl:
        cached_crawl = _session.get_crawl(question) if not custom_queries else None
        if cached_crawl is not None:
            logger.info("[pipeline] Stage 2: 캐시 히트 — %d건", len(cached_crawl))
            crawl_results = cached_crawl
            t_crawl.mark_status("cache_hit")
        else:
            crawl_results = await _crawl_with_retries(
                question, search_plan, crawler_service, search_service, label="pipeline",
            )
            if crawl_results:
                _session.set_crawl(question, crawl_results)
            if not crawl_results:
                t_crawl.mark_status("empty")

    if not crawl_results:
        return _CRAWL_EMPTY_MSG

    logger.info("[pipeline] Stage 2 완료: %d건 수집", len(crawl_results))

    # ── 크롤링 완료 → OLTA JS 타이머 중단 (이벤트 루프 해방) ──
    await crawler_service.quiet_page()

    # ── Stage 3: 랭킹 (search_queries 전달) ──
    logger.info("[pipeline] Stage 3: 임베딩 랭킹 시작")
    async with stage_timed("ranking", req_id=req_id):
        ranked = await embedding_service.rank_results(
            question,
            crawl_results,
            preferred_year=search_plan.detected_year,
            prefer_latest=search_plan.prefer_latest,
            search_queries=search_plan.search_queries,
        )

    # ── Stage 3-B: 관련도 하한 필터 ──
    if len(ranked) > 5:
        min_score = ranked[0].relevance_score * settings.min_relevance_ratio
        filtered = [r for r in ranked if r.relevance_score >= min_score]
        ranked = filtered if len(filtered) >= 5 else ranked[:max(5, len(filtered))]

    # 근거 그루핑에 투입할 결과 수 제한
    max_for_grouping = min(len(ranked), settings.answer_context_top_k)
    ranked = ranked[:max_for_grouping]
    _session.set_ranked(question, ranked)
    logger.info("[pipeline] Stage 3 완료: %d건 랭킹 (상위 %d건 사용)", len(crawl_results), len(ranked))

    # ── Stage 4: 근거 그루핑 + 요약 (타임아웃 보호) ──
    logger.info("[pipeline] Stage 4: 근거 그루핑 + 요약 시작 (%d건)", len(ranked))
    async with stage_timed("evidence_grouping", req_id=req_id) as t_group:
        try:
            evidence_groups = await asyncio.wait_for(
                evidence_group_service.group(question, ranked),
                timeout=120,
            )
        except asyncio.TimeoutError:
            logger.warning("[pipeline] Stage 4: 근거 그루핑 타임아웃(120s) — heuristic fallback 사용")
            evidence_groups = evidence_group_service._group_by_heuristics(question, ranked)
            t_group.mark_status("timeout_fallback")

        logger.info("[pipeline] Stage 4-A 완료: %d개 근거 묶음", len(evidence_groups))

        try:
            evidence_slots = await asyncio.wait_for(
                evidence_summary_service.summarize(question, evidence_groups, ranked),
                timeout=120,
            )
        except asyncio.TimeoutError:
            logger.warning("[pipeline] Stage 4: 근거 요약 타임아웃(120s) — fallback 사용")
            evidence_slots = [
                evidence_summary_service._fallback_summary(
                    g,
                    [r for r in ranked if r.id in g.source_ids],
                )
                for g in evidence_groups
                if any(r.id in g.source_ids for r in ranked)
            ]
            t_group.mark_status("timeout_fallback")

    _session.set_evidence(question, evidence_slots)
    logger.info(
        "[pipeline] Stage 4 완료: %d건 → 랭킹 %d건 → 근거묶음 %d개 → 근거슬롯 %d개",
        len(crawl_results), len(ranked), len(evidence_groups), len(evidence_slots),
    )

    # ── Stage 5: LLM 답변 생성 (타임아웃 보호) ──
    logger.info("[pipeline] Stage 5: LLM 답변 생성 시작")
    async with stage_timed("drafting", req_id=req_id) as t_draft:
        try:
            draft = await asyncio.wait_for(
                llm_service.generate_draft(
                    question=question,
                    crawl_results=ranked,
                    evidence_slots=evidence_slots,
                ),
                timeout=90,
            )
        except asyncio.TimeoutError:
            logger.warning("[pipeline] Stage 5: LLM 답변 생성 타임아웃(90s) — fallback 사용")
            draft = await llm_service._fallback_generate(question, ranked, None)
            t_draft.mark_status("timeout_fallback")
    logger.info("[pipeline] Stage 5 완료")

    # ── Stage 6: 답변 검증 + 자동 수정 (선택적) ──
    verification_result = None
    if not skip_verification:
        async with stage_timed("verifying", req_id=req_id):
            verification_result = await _run_verification(
                draft, ranked, evidence_slots, question, llm_service,
            )

    # ── Quality metric emission (design-doc 00 schema) ──
    try:
        vr = verification_result
        tier = getattr(vr, "confidence_label", None) if vr else None
        overall = getattr(vr, "overall_confidence", None) if vr else None
        citation = getattr(vr, "citation_coverage", None) if vr else None
        quality_metric(
            req_id=req_id,
            verified_citation_rate=citation,
            hallucination_rate=None,          # Plan 3 이전에는 null
            coverage_score=None,               # Plan 3 이전에는 null
            revision_triggered=getattr(vr, "revision_triggered", None) if vr else None,
            revision_rounds=getattr(vr, "revision_rounds", None) if vr else None,
            confidence_tier=tier,
            overall_confidence=overall,
            golden_set_id=golden_set_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("quality_metric emit 실패: %s", exc)

    # ── 결과 포매팅 ──
    sections = []

    # 답변 본문
    sections.append("## 답변\n")
    sections.append(draft.answer)

    # 검증 결과 (있을 경우)
    if verification_result:
        sections.append("\n\n---\n\n## 검증 결과")
        sections.append(f"- 신뢰도: {verification_result.confidence_label} ({verification_result.overall_confidence:.0%})")
        sections.append(f"  - 주장 신뢰도: {verification_result.claim_confidence:.0%}")
        sections.append(f"  - 출처 신뢰도: {verification_result.source_confidence:.0%}")
        if verification_result.slot_confidence:
            sections.append(f"  - 근거묶음 신뢰도: {verification_result.slot_confidence:.0%}")
        sections.append(f"  - 출처 커버리지: {verification_result.citation_coverage:.0%}")
        if verification_result.removed_claims:
            sections.append(f"- 제거된 주장: {len(verification_result.removed_claims)}건")
            for claim in verification_result.removed_claims[:3]:
                sections.append(f"  - {claim[:80]}")
        if verification_result.modified_claims:
            sections.append(f"- 수정된 주장: {len(verification_result.modified_claims)}건")
            for mod in verification_result.modified_claims[:3]:
                sections.append(f"  - {mod['original'][:60]} → {mod['corrected'][:60]}")
        if verification_result.warnings:
            sections.append(f"- 경고: {len(verification_result.warnings)}건")
            for w in verification_result.warnings[:5]:
                sections.append(f"  - {w}")
        if verification_result.critical_issues:
            sections.append(f"- 핵심 이슈: {len(verification_result.critical_issues)}건")
            for ci in verification_result.critical_issues[:3]:
                sections.append(f"  - {ci}")

    # 검색 분석
    sections.append("\n\n---\n\n## 검색 분석")
    sections.append(f"- 질문 유형: {search_plan.question_type}")
    sections.append(f"- 주요 세목: {search_plan.primary_tax_type or '미지정'}")
    sections.append(f"- 주요 쟁점: {search_plan.primary_topic or '미지정'}")
    sections.append("- 검색어 조합:")
    for i, q in enumerate(search_plan.search_queries, 1):
        sections.append(f'  {i}. "{q}"')
    sections.append(f"- 우선 BBS 게시판: {', '.join(search_plan.priority_bbs_boards[:3]) or '기본'}")
    sections.append(f"- 수집 범위: {', '.join(search_plan.collection_focus) or '전체'}")
    sections.append(f"- 연도 기준: {search_plan.weighting_label}")

    # 수집 통계
    sections.append("\n## 수집 통계")
    sections.append(
        f"- {len(crawl_results)}건 수집 → {len(ranked)}건 랭킹 → "
        f"{len(evidence_slots)}개 근거 묶음"
    )

    # 검색어별 수집 기여도
    query_counts: dict[str, int] = {}
    for r in ranked:
        sq = r.source_query or "미분류"
        query_counts[sq] = query_counts.get(sq, 0) + 1
    if any(sq != "미분류" for sq in query_counts):
        sections.append("\n## 검색어별 수집 기여도")
        for sq, count in sorted(query_counts.items(), key=lambda x: -x[1]):
            sections.append(f'  - "{sq}": {count}건')

    # 인용 출처
    cited_results = [r for r in ranked if r.id in (draft.cited_sources or [])]
    if not cited_results:
        cited_results = ranked[:10]

    sections.append("\n## 인용 출처")
    for i, r in enumerate(cited_results, 1):
        year = f" ({r.document_year})" if r.document_year else ""
        sections.append(f"{i}. **[{r.id}]** {r.title}{year} — {r.type}")
        if r.url:
            sections.append(f"   URL: {r.url}")

    # 근거 묶음 요약
    if evidence_slots:
        sections.append("\n## 근거 묶음 요약")
        for slot in evidence_slots:
            sections.append(f"\n### {slot.title}")
            if slot.issue:
                sections.append(f"- 쟁점: {slot.issue}")
            if slot.conclusion:
                sections.append(f"- 결론: {slot.conclusion}")
            if slot.key_points:
                for kp in slot.key_points[:3]:
                    sections.append(f"- {kp}")

    return "\n".join(sections)


# ═══════════════════════════════════════════
# 공통: 답변 검증 파이프라인
# ═══════════════════════════════════════════
async def _run_verification(draft, ranked, evidence_slots, question, llm_service):
    """답변 검증을 수행하고, 신뢰도가 낮으면 자동 수정한다.

    Returns:
        VerificationResult 또는 None (타임아웃/실패 시)
    """
    from app.config import get_settings
    from app.services.verification.content_verifier import content_verifier
    from app.services.verification.grouped_answer_verifier import grouped_answer_verifier
    from app.services.verification.source_verifier import source_verifier
    from app.services.verification.verification_aggregator import verification_aggregator

    settings = get_settings()
    logger.info("[pipeline] Stage 6: 답변 검증 시작")

    try:
        # 출처 검증 + 내용 검증 병렬 실행
        verify_tasks = [
            source_verifier.verify(draft.answer, ranked),
            content_verifier.verify(draft.answer, ranked),
        ]
        # 근거묶음 검증 (evidence_slots이 있을 때만)
        if evidence_slots:
            verify_tasks.append(
                grouped_answer_verifier.verify(draft.answer, evidence_slots),
            )

        verify_results = await asyncio.wait_for(
            asyncio.gather(*verify_tasks, return_exceptions=True),
            timeout=60,
        )

        # 결과 언패킹 (예외는 빈 리스트로 대체)
        source_verifs = verify_results[0] if not isinstance(verify_results[0], Exception) else []
        content_claims = verify_results[1] if not isinstance(verify_results[1], Exception) else []
        slot_verifs = (
            verify_results[2]
            if len(verify_results) > 2 and not isinstance(verify_results[2], Exception)
            else []
        )

        if isinstance(source_verifs, Exception):
            logger.warning("[pipeline] Stage 6: 출처 검증 실패: %s", source_verifs)
            source_verifs = []
        if isinstance(content_claims, Exception):
            logger.warning("[pipeline] Stage 6: 내용 검증 실패: %s", content_claims)
            content_claims = []

        # 검증 결과 집계
        verification_result = verification_aggregator.aggregate(
            source_verifs, content_claims, slot_verifs,
        )

        logger.info(
            "[pipeline] Stage 6 완료: confidence=%.2f (%s), warnings=%d, critical=%d",
            verification_result.overall_confidence,
            verification_result.confidence_label,
            len(verification_result.warnings),
            len(verification_result.critical_issues),
        )

        # 신뢰도가 낮으면 자동 수정
        if verification_result.overall_confidence < settings.verification_target_confidence:
            logger.info(
                "[pipeline] Stage 6-B: 신뢰도 %.2f < %.2f — 답변 수정 시작",
                verification_result.overall_confidence,
                settings.verification_target_confidence,
            )
            try:
                revised = await asyncio.wait_for(
                    llm_service.revise_draft(
                        question, draft.answer, verification_result,
                        ranked, evidence_slots,
                    ),
                    timeout=60,
                )
                draft.answer = revised.answer
                draft.cited_sources = revised.cited_sources
                logger.info("[pipeline] Stage 6-B 완료: 답변 수정됨")
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning("[pipeline] Stage 6-B: 답변 수정 실패 — 원본 유지: %s", exc)

        return verification_result

    except asyncio.TimeoutError:
        logger.warning("[pipeline] Stage 6: 검증 타임아웃(60s) — 검증 건너뜀")
        return None
    except Exception as exc:
        logger.warning("[pipeline] Stage 6: 검증 실패 — 검증 건너뜀: %s", exc)
        return None


# ═══════════════════════════════════════════
# 정리 및 진입점
# ═══════════════════════════════════════════
def _cleanup():
    """프로세스 종료 시 Playwright 브라우저 정리."""
    try:
        from app.services.crawler_service import crawler_service

        loop = asyncio.new_event_loop()
        loop.run_until_complete(crawler_service.close_browser())
        loop.close()
    except Exception:
        pass


atexit.register(_cleanup)

if __name__ == "__main__":
    mcp.run(transport="stdio")
