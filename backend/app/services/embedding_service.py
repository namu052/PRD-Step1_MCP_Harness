import asyncio
import logging

from app.config import get_settings
from app import feature_flags as _ff
from app.models.schemas import CrawlResult
from app.services.openai_service import openai_service
from app.services.retrieval import hybrid_score

logger = logging.getLogger(__name__)


class EmbeddingService:
    async def rank_results(
        self,
        question: str,
        results: list[CrawlResult],
        top_k: int | None = None,
        preferred_year: int | None = None,
        prefer_latest: bool = True,
        search_queries: list[str] | None = None,
    ) -> list[CrawlResult]:
        """임베딩 랭킹을 별도 스레드에서 동기적으로 실행한다.

        concurrent.futures를 사용하여 이벤트 루프 콜백 지연 문제를 회피한다.
        """
        import concurrent.futures
        import time as _time

        if not results:
            return []

        _t0 = _time.monotonic()
        logger.info("▶ rank_results 시작: %d건", len(results))

        # concurrent.futures로 직접 실행 — asyncio.to_thread보다 이벤트 루프 의존도 낮음
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = loop.run_in_executor(
                executor,
                self._rank_results_sync,
                question, results, top_k, preferred_year, prefer_latest, search_queries,
            )
            try:
                ranked = await asyncio.wait_for(future, timeout=120)
            except asyncio.TimeoutError:
                logger.error("▶ rank_results 타임아웃(120s) — 키워드 fallback 사용")
                ranked = self._keyword_fallback(question, results, top_k, preferred_year, prefer_latest, search_queries)

        logger.info("▶ rank_results 완료: %d건 → %d건 (+%.1fs)", len(results), len(ranked), _time.monotonic() - _t0)
        return ranked

    def _keyword_fallback(
        self,
        question: str,
        results: list[CrawlResult],
        top_k: int | None = None,
        preferred_year: int | None = None,
        prefer_latest: bool = True,
        search_queries: list[str] | None = None,
    ) -> list[CrawlResult]:
        settings = get_settings()
        limit = top_k or settings.answer_context_top_k
        latest_year = max((r.document_year or 0 for r in results), default=0) or None
        question_terms = self._tokenize(question)
        if search_queries:
            for sq in search_queries:
                question_terms.update(self._tokenize(sq))
        ranked = sorted(
            results,
            key=lambda r: self._score_result(
                r, question_terms,
                preferred_year=preferred_year,
                latest_year=latest_year,
                prefer_latest=prefer_latest,
            ),
            reverse=True,
        )
        return self._select_diverse_results(ranked, limit)

    def _rank_results_sync(
        self,
        question: str,
        results: list[CrawlResult],
        top_k: int | None = None,
        preferred_year: int | None = None,
        prefer_latest: bool = True,
        search_queries: list[str] | None = None,
    ) -> list[CrawlResult]:
        """동기 전용: 임베딩 API 호출 + 스코어링 + 다양성 선택을 스레드에서 실행."""
        import time as _time
        _t0 = _time.monotonic()
        settings = get_settings()
        limit = top_k or settings.answer_context_top_k
        latest_year = max((r.document_year or 0 for r in results), default=0) or None

        try:
            logger.info("  [thread] 임베딩 텍스트 준비 시작")
            doc_texts = [self._build_embedding_text(r) for r in results]
            texts = [question, *doc_texts]
            logger.info("  [thread] 임베딩 텍스트 준비 완료 (+%.1fs), API 호출 시작", _time.monotonic() - _t0)

            # urllib로 직접 호출 — httpx/OpenAI SDK의 이벤트 루프 경합 완전 우회
            embeddings = self._call_embeddings_urllib(
                settings.openai_api_key,
                settings.openai_embedding_model,
                texts,
            )
            logger.info("  [thread] API 응답 수신 (+%.1fs)", _time.monotonic() - _t0)

            if len(embeddings) != len(results) + 1:
                raise RuntimeError("unexpected embedding length")

            logger.info("  [thread] 임베딩 완료: %d건, 스코어링 시작 (+%.1fs)", len(results), _time.monotonic() - _t0)

            question_embedding = embeddings[0]
            cosines = [
                openai_service.cosine_similarity(question_embedding, embeddings[i + 1])
                for i in range(len(results))
            ]
            use_hybrid = _ff.flags.retrieval_mode == "hybrid"
            hybrid_vals: list[float] = []
            if use_hybrid:
                hybrid_vals = hybrid_score(
                    question, results, cosines, alpha=_ff.flags.retrieval_alpha,
                )
            scored = []
            for index, result in enumerate(results):
                semantic = cosines[index]
                overlap = self._term_overlap_score(question, result, search_queries)
                year_bonus = self._year_bonus(
                    result.document_year,
                    preferred_year=preferred_year,
                    latest_year=latest_year,
                    prefer_latest=prefer_latest,
                )
                if use_hybrid:
                    # hybrid = prior * (α*cos + (1-α)*bm25_norm) → semantic/overlap 가중과 독립 결합
                    combined = (
                        hybrid_vals[index] * settings.ranking_semantic_weight
                        + overlap * settings.ranking_overlap_weight
                        + result.relevance_score * settings.ranking_position_weight
                        + year_bonus * settings.ranking_year_weight
                    )
                else:
                    combined = (
                        semantic * settings.ranking_semantic_weight
                        + overlap * settings.ranking_overlap_weight
                        + result.relevance_score * settings.ranking_position_weight
                        + year_bonus * settings.ranking_year_weight
                    )
                scored.append((combined, result))

            logger.info("  [thread] 스코어링 완료 (+%.1fs), 다양성 선택 시작", _time.monotonic() - _t0)
            scored.sort(key=lambda item: item[0], reverse=True)
            result = self._select_diverse_results([r for _, r in scored], limit)
            logger.info("  [thread] _rank_results_sync 완료: %d건 선택 (+%.1fs)", len(result), _time.monotonic() - _t0)
            return result
        except Exception:
            logger.warning("임베딩 랭킹 실패 — 키워드 fallback 사용", exc_info=True)
            question_terms = self._tokenize(question)
            if search_queries:
                for sq in search_queries:
                    question_terms.update(self._tokenize(sq))
            ranked = sorted(
                results,
                key=lambda r: self._score_result(
                    r, question_terms,
                    preferred_year=preferred_year,
                    latest_year=latest_year,
                    prefer_latest=prefer_latest,
                ),
                reverse=True,
            )
            return self._select_diverse_results(ranked, limit)

    @staticmethod
    def _call_embeddings_urllib(api_key: str, model: str, texts: list[str]) -> list[list[float]]:
        """urllib로 OpenAI Embeddings API를 직접 호출한다.

        httpx/OpenAI SDK가 내부적으로 이벤트 루프에 의존하여
        Playwright 환경에서 블로킹되는 문제를 완전히 우회한다.
        """
        import json
        import urllib.request

        url = "https://api.openai.com/v1/embeddings"
        payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        ordered = sorted(body["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in ordered]

    def _build_embedding_text(self, result: CrawlResult) -> str:
        settings = get_settings()
        return f"{result.title} {result.preview} {result.content[: settings.embedding_content_limit]}"

    def _score_result(
        self,
        result: CrawlResult,
        question_terms: set[str],
        preferred_year: int | None = None,
        latest_year: int | None = None,
        prefer_latest: bool = True,
    ) -> tuple[float, float, float, float]:
        overlap = self._term_overlap_score(" ".join(question_terms), result)
        year_bonus = self._year_bonus(
            result.document_year,
            preferred_year=preferred_year,
            latest_year=latest_year,
            prefer_latest=prefer_latest,
        )
        return (overlap + result.relevance_score + year_bonus, year_bonus, result.relevance_score, overlap)

    def _tokenize(self, text: str) -> set[str]:
        return {token.strip().lower() for token in text.split() if token.strip()}

    def _term_overlap_score(
        self,
        question: str,
        result: CrawlResult,
        search_queries: list[str] | None = None,
    ) -> float:
        question_terms = self._tokenize(question)
        if search_queries:
            for sq in search_queries:
                question_terms.update(self._tokenize(sq))
        haystack = f"{result.title} {result.preview} {result.content[:600]}".lower()
        return float(sum(1 for term in question_terms if term in haystack))

    def _year_bonus(
        self,
        document_year: int | None,
        preferred_year: int | None = None,
        latest_year: int | None = None,
        prefer_latest: bool = True,
    ) -> float:
        if not document_year:
            return 0.0

        if preferred_year is not None:
            distance = abs(document_year - preferred_year)
            return max(0.0, 1.2 - (min(distance, 12) * 0.1))

        if prefer_latest and latest_year:
            distance = max(0, latest_year - document_year)
            return max(0.0, 0.9 - (min(distance, 9) * 0.1))

        return 0.0

    def _select_diverse_results(self, ranked: list[CrawlResult], limit: int) -> list[CrawlResult]:
        if len(ranked) <= limit:
            return ranked

        settings = get_settings()
        per_type_quota = max(2, limit // settings.ranking_diversity_divisor)
        selected: list[CrawlResult] = []
        seen_ids = set()
        type_counts: dict[str, int] = {}

        for result in ranked:
            current_count = type_counts.get(result.type, 0)
            if current_count >= per_type_quota:
                continue
            selected.append(result)
            seen_ids.add(result.id)
            type_counts[result.type] = current_count + 1
            if len(selected) >= limit:
                return selected

        for result in ranked:
            if result.id in seen_ids:
                continue
            selected.append(result)
            if len(selected) >= limit:
                break

        return selected


embedding_service = EmbeddingService()
