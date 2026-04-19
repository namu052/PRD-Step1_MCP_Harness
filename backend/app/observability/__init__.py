"""Observability primitives for pipeline/quality metrics (design-doc 00)."""
from .timing import stage_timed, quality_metric, new_req_id, set_metrics_root

__all__ = ["stage_timed", "quality_metric", "new_req_id", "set_metrics_root"]
