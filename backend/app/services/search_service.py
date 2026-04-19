import logging
import re
from dataclasses import dataclass, field

from app.config import get_settings
from app.prompts.search_extraction_prompt import (
    KEYWORD_EXTRACTION_SCHEMA,
    KEYWORD_EXTRACTION_SYSTEM,
)
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)

TAX_TERMS = [
    "취득세",
    "재산세",
    "등록면허세",
    "자동차세",
    "주민세",
    "지방세",
    "지방소득세",
    "지방교육세",
    "지역자원시설세",
    "레저세",
    "담배소비세",
]

TOPIC_TERMS = [
    "감면",
    "환급",
    "신고",
    "납부",
    "비과세",
    "과세",
    "판례",
    "유권해석",
    "추징",
    "세율",
    "과세표준",
    "납세의무",
    "가산세",
    "경정청구",
    "유예",
    "연납",
    "분할납부",
    "불복",
    "심판",
]

_BBS_PRIORITY_MAP = {
    "감면·적용요건형": ["질의응답", "지방세상담", "실무편람", "FAQ", "참고자료"],
    "판례·결정례 비교형": ["쟁송사무지원 사례", "참고자료", "쟁송사무위크숍 자료", "질의응답"],
    "유권해석 중심형": ["질의응답", "지방세상담", "참고자료", "실무편람"],
    "절차·기한형": ["질의응답", "FAQ", "매뉴얼", "실무편람", "이용안내 Q&A"],
    "환급·구제형": ["질의응답", "지방세상담", "쟁송사무지원 사례", "참고자료"],
    "일반 종합형": ["질의응답", "지방세상담", "실무편람", "참고자료", "FAQ"],
}

_NON_TAX_PATTERNS = re.compile(
    r"^(안녕|반갑|감사|고마워|수고|헬로|하이|hello|hi|hey|thanks|thank you|bye|good)\b",
    re.IGNORECASE,
)


@dataclass
class SearchPlan:
    question_type: str
    categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    detected_year: int | None = None
    prefer_latest: bool = True
    analysis_focus: list[str] = field(default_factory=list)
    collection_focus: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    primary_tax_type: str = ""
    primary_topic: str = ""
    priority_bbs_boards: list[str] = field(default_factory=list)

    @property
    def weighting_label(self) -> str:
        if self.detected_year:
            return f"{self.detected_year}년과 가까운 자료를 우선 검토"
        return "최신 자료를 우선 검토"

    def to_notice(self) -> str:
        focus_text = ", ".join(self.analysis_focus) if self.analysis_focus else "관련 법령과 해석 흐름 종합"
        collections = ", ".join(self.collection_focus) if self.collection_focus else "전체 컬렉션"
        queries_text = ", ".join(f"'{q}'" for q in self.search_queries[:3]) if self.search_queries else "질문 원문"
        return (
            f"질문 분석 완료: {self.question_type}. "
            f"수집 계획은 {collections}에서 {queries_text} 중심으로 자료를 모으고, "
            f"{self.weighting_label} 기준으로 정렬한 뒤 {focus_text} 순서로 답변을 구성합니다."
        )


class SearchService:
    async def extract_keywords(self, question: str) -> list[str]:
        return (await self.build_search_plan(question)).keywords

    def _is_non_tax_question(self, text: str) -> bool:
        if len(text) < 6 and not any(t in text for t in TAX_TERMS):
            return True
        if _NON_TAX_PATTERNS.match(text) and not any(t in text for t in TAX_TERMS):
            return True
        return False

    async def build_search_plan(self, question: str) -> SearchPlan:
        settings = get_settings()
        normalized = re.sub(r"\s+", " ", question).strip()
        if not normalized or self._is_non_tax_question(normalized):
            return SearchPlan(question_type="일반 질의", keywords=[], categories=[])

        detected_year = self._extract_year(normalized)
        question_type = self._classify_question_type(normalized)
        categories = self._select_categories(question_type, normalized)
        analysis_focus = self._build_analysis_focus(question_type, normalized)
        collection_focus = [self._category_label(c) for c in categories]
        priority_bbs_boards = _BBS_PRIORITY_MAP.get(question_type, _BBS_PRIORITY_MAP["일반 종합형"])

        # LLM 기반 검색어 생성
        if settings.search_use_llm_extraction:
            extraction = await self._llm_extract(normalized)
        else:
            extraction = self._extract_without_llm_full(normalized)

        keywords = extraction["keywords"][:settings.search_max_keywords]
        search_queries = extraction["search_queries"][:settings.search_max_queries]
        primary_tax_type = extraction.get("primary_tax_type", "")
        primary_topic = extraction.get("primary_topic", "")

        # search_queries가 비어 있으면 키워드로 생성
        if not search_queries:
            search_queries = self._build_queries_from_keywords(normalized, keywords)

        return SearchPlan(
            question_type=question_type,
            categories=categories,
            keywords=keywords,
            detected_year=detected_year,
            prefer_latest=detected_year is None,
            analysis_focus=analysis_focus,
            collection_focus=collection_focus,
            search_queries=search_queries,
            primary_tax_type=primary_tax_type,
            primary_topic=primary_topic,
            priority_bbs_boards=priority_bbs_boards,
        )

    # ── LLM 기반 추출 (search_queries + keywords) ──

    async def _llm_extract(self, question: str) -> dict:
        settings = get_settings()
        fallback_kw = self._extract_without_llm(question)
        try:
            payload, _ = await openai_service.create_json(
                model=settings.openai_verification_model,
                system_prompt=KEYWORD_EXTRACTION_SYSTEM,
                user_prompt=f"질문: {question}",
                schema_name="keyword_extraction",
                schema=KEYWORD_EXTRACTION_SCHEMA,
                temperature=0.0,
                max_tokens=800,
            )
        except Exception:
            logger.warning("LLM 검색어 추출 실패 — fallback 사용", exc_info=True)
            return self._extract_without_llm_full(question)

        # search_queries 정리
        raw_queries = payload.get("search_queries") or []
        search_queries = self._clean_queries(raw_queries, question)

        # keywords 병합 (LLM + fallback)
        combined_kw = [
            *(payload.get("keywords") or []),
            *(payload.get("synonyms") or []),
            *(payload.get("legal_refs") or []),
            *fallback_kw,
        ]
        keywords = self._dedup_list(combined_kw)

        primary_tax_type = (payload.get("primary_tax_type") or "").strip()
        primary_topic = (payload.get("primary_topic") or "").strip()

        logger.info(
            "검색어 생성: queries=%s, keywords=%d개, tax=%s, topic=%s",
            search_queries, len(keywords), primary_tax_type, primary_topic,
        )
        return {
            "search_queries": search_queries,
            "keywords": keywords,
            "primary_tax_type": primary_tax_type,
            "primary_topic": primary_topic,
        }

    def _clean_queries(self, raw_queries: list[str], question: str) -> list[str]:
        """LLM이 생성한 검색어를 정리: 길이 제한, 원문 그대로 사용 방지, 중복 제거."""
        cleaned = []
        seen = set()
        normalized_q = re.sub(r"\s+", "", question)
        for q in raw_queries:
            q = re.sub(r"\s+", " ", str(q or "")).strip()
            if not q or len(q) < 3 or len(q) > 40:
                continue
            # 질문 원문과 거의 동일한 검색어 제거
            if re.sub(r"\s+", "", q) == normalized_q:
                continue
            key = q.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(q)
        return cleaned

    # ── 비-LLM 추출 ──

    def _extract_without_llm(self, question: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", question).strip()
        if not normalized:
            return []

        keywords = []
        for tax in TAX_TERMS:
            if tax in normalized:
                for topic in TOPIC_TERMS:
                    if topic in normalized:
                        keywords.append(f"{tax} {topic}")
                keywords.append(tax)

        compact = re.sub(r"[?.,()]", " ", normalized)
        compact = re.sub(r"\s+", " ", compact).strip()
        if compact and compact not in keywords:
            keywords.append(compact)

        return self._dedup_list(keywords)[:3]

    def _extract_without_llm_full(self, question: str) -> dict:
        """LLM 없이 키워드 + 검색어를 모두 생성 (fallback용)."""
        keywords = self._extract_without_llm(question)
        search_queries = self._build_queries_from_keywords(question, keywords)
        tax_type = next((t for t in TAX_TERMS if t in question), "지방세")
        topic = next((t for t in TOPIC_TERMS if t in question), "")
        return {
            "search_queries": search_queries,
            "keywords": keywords,
            "primary_tax_type": tax_type,
            "primary_topic": topic,
        }

    # ── 키워드 → 검색어 변환 ──

    def _build_queries_from_keywords(self, question: str, keywords: list[str]) -> list[str]:
        """키워드 리스트를 조합해 OLTA 검색용 쿼리를 생성한다."""
        queries = []

        # 전략1: 질문 핵심 축약 (조사/기호 제거)
        compact = re.sub(r"[?.,()에서을를이가의은는도에게로부터]", " ", question)
        compact = re.sub(r"\s+", " ", compact).strip()
        if 5 <= len(compact) <= 30:
            queries.append(compact)
        elif len(compact) > 30:
            queries.append(compact[:30].rsplit(" ", 1)[0])

        # 전략2: 세목 + 쟁점 조합
        tax = next((t for t in TAX_TERMS if t in question), None)
        topic = next((t for t in TOPIC_TERMS if t in question), None)
        if tax and topic and f"{tax} {topic}" not in queries:
            queries.append(f"{tax} {topic}")

        # 전략3: 상위 키워드 2~3개 공백 결합
        if len(keywords) >= 2:
            combo = " ".join(keywords[:3])
            if combo not in queries and len(combo) <= 30:
                queries.append(combo)

        return self._dedup_list(queries)[:4]

    def _build_fallback_queries(self, question: str, keywords: list[str]) -> list[str]:
        """0건 수집 시 재시도용 — 키워드를 다르게 조합."""
        queries = []

        # 개별 키워드를 단독 검색어로
        for kw in keywords[:3]:
            if len(kw) >= 2:
                queries.append(kw)

        # 세목만 단독
        tax = next((t for t in TAX_TERMS if t in question), None)
        if tax and tax not in queries:
            queries.append(tax)

        return self._dedup_list(queries)[:4]

    # ── 유틸리티 ──

    @staticmethod
    def _dedup_list(items: list[str]) -> list[str]:
        deduped = []
        seen = set()
        for item in items:
            value = re.sub(r"\s+", " ", str(item or "")).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _extract_year(self, text: str) -> int | None:
        match = re.search(r"(?<!\d)((?:19|20)\d{2})(?:년)?(?!\d)", text)
        return int(match.group(1)) if match else None

    def _classify_question_type(self, question: str) -> str:
        if any(token in question for token in ["판례", "판결", "심판", "결정례"]):
            return "판례·결정례 비교형"
        if any(token in question for token in ["유권해석", "법제처", "행안부", "해석"]):
            return "유권해석 중심형"
        if any(token in question for token in ["감면", "비과세", "면제", "대상", "요건"]):
            return "감면·적용요건형"
        if any(token in question for token in ["신고", "납부", "기한", "절차", "제출"]):
            return "절차·기한형"
        if any(token in question for token in ["환급", "경정청구", "불복", "구제"]):
            return "환급·구제형"
        return "일반 종합형"

    def _select_categories(self, question_type: str, question: str) -> list[str]:
        if question_type == "판례·결정례 비교형":
            return ["case_search", "interpret_search"]
        if question_type == "유권해석 중심형":
            return ["law_search", "interpret_search"]
        if question_type == "절차·기한형":
            return ["law_search", "interpret_search"]
        if question_type == "환급·구제형":
            return ["case_search", "interpret_search", "law_search"]
        if question_type == "감면·적용요건형":
            return ["law_search", "interpret_search", "case_search"]
        if "판례" in question or "해석" in question:
            return ["case_search", "interpret_search", "law_search"]
        return ["law_search", "interpret_search", "case_search"]

    def _build_analysis_focus(self, question_type: str, question: str) -> list[str]:
        focus = []
        if question_type in {"감면·적용요건형", "일반 종합형"}:
            focus.extend(["적용 요건", "예외·제한", "실무상 주의사항"])
        if question_type in {"판례·결정례 비교형", "환급·구제형"}:
            focus.extend(["사실관계 차이", "판단 충돌 여부", "구제 가능성"])
        if question_type in {"유권해석 중심형", "절차·기한형"}:
            focus.extend(["법령 문언", "행정해석 흐름", "실무 절차"])
        if self._extract_year(question):
            focus.append("특정 연도와 가까운 자료 비교")
        elif "최신" in question or "최근" in question:
            focus.append("최신 해석 우선 검토")
        return list(dict.fromkeys(focus))

    def _category_label(self, category: str) -> str:
        labels = {
            "law_search": "법령·유권해석",
            "interpret_search": "해석·심판",
            "case_search": "판례·결정례",
        }
        return labels.get(category, category)


search_service = SearchService()
