"""Verified guidance is shown only when it mentions the problem, not just the crop."""

from app.services import chat_orchestrator
from app.services import rag_service
from test_chat_orchestrator import seeded  # noqa: F401


class _Turn:
    def __init__(self):
        self.language = "en"
        self.messages = []
        self.steps = []
        self.evidence_ids = []

    def step(self, name, **kw):
        self.steps.append((name, kw))

    def say(self, text, kind="advisory", **kw):
        self.messages.append((kind, text))


def _fake(items):
    return lambda query, crop, top_k=2: {"status": "ok", "results": items}


def test_unrelated_record_is_dropped(monkeypatch):
    items = [{"id": 1, "text": "Bacillus subtilis is listed for Banana against Sigatoka.", "source": "PPQS"}]
    monkeypatch.setattr(rag_service, "retrieve_verified_evidence", _fake(items))
    turn = _Turn()
    chat_orchestrator._knowledge(turn, "Banana", "Bract mosaic virus")
    assert turn.messages == []
    assert turn.evidence_ids == []


def test_matching_record_is_kept(monkeypatch):
    items = [{"id": 2, "text": "Chlorantraniliprole is listed for Chilli against Fruit borer.", "source": "PPQS"}]
    monkeypatch.setattr(rag_service, "retrieve_verified_evidence", _fake(items))
    turn = _Turn()
    chat_orchestrator._knowledge(turn, "Chilli", "fruit borer")
    assert len(turn.messages) == 1 and "Fruit borer" in turn.messages[0][1]
    assert turn.evidence_ids == [2]


def test_crop_only_topic_shows_nothing(monkeypatch):
    items = [{"id": 3, "text": "Chlorantraniliprole is listed for Chilli against Fruit borer.", "source": "PPQS"}]
    monkeypatch.setattr(rag_service, "retrieve_verified_evidence", _fake(items))
    turn = _Turn()
    chat_orchestrator._knowledge(turn, "Chilli", "Chilli")
    assert turn.messages == []
