"""Stub ContextualBandit — not yet implemented."""


class ContextualBandit:
    """Placeholder bandit. Always returns is_fitted=False."""

    def __init__(self):
        self.is_fitted = False

    def fit(self, *args, **kwargs):
        pass

    def recommend(self, ctx: dict) -> dict:
        return {"recommended_market": "skip", "confidence": 0.0, "segment": "none"}

    def get_segment_summary(self) -> dict:
        return {}
