import logging
from app.services.twenty_crm import STAGES

logger = logging.getLogger(__name__)

STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}

AUTO_ADVANCE = {
    "CONTACTED": "OPENED",
    "OPENED": "REPLIED",
}


class FunnelManager:
    def __init__(self, twenty_crm=None):
        self.twenty = twenty_crm

    def next_stage(self, current: str, event: str | None = None) -> str:
        if event == "open":
            return self._advance(current, "OPENED")
        elif event == "click":
            target = "REPLIED" if STAGE_ORDER.get(current, 0) < STAGE_ORDER.get("REPLIED", 99) else current
            return self._advance(current, "REPLIED")
        elif event == "reply":
            return self._advance(current, "REPLIED")
        return current

    def _advance(self, current: str, target: str) -> str:
        if STAGE_ORDER.get(current, -1) < STAGE_ORDER.get(target, -1):
            return target
        return current

    def can_advance_to(self, current: str, target: str) -> bool:
        return STAGE_ORDER.get(target, -1) > STAGE_ORDER.get(current, -1)

    def stages_summary(self, lead_counts: dict[str, int]) -> list[dict]:
        return [
            {"stage": s, "count": lead_counts.get(s, 0), "order": i}
            for i, s in enumerate(STAGES)
        ]
