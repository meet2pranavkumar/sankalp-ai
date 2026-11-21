from app.services import finalizer


def test_optional_judge_is_none_when_the_judge_is_not_set_up(monkeypatch):
    def not_set_up():
        raise RuntimeError("Unknown JUDGE_BACKEND")

    monkeypatch.setattr(finalizer, "get_judge", not_set_up)
    assert finalizer.optional_judge() is None


def test_optional_judge_returns_the_judge_when_it_is_set_up(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(finalizer, "get_judge", lambda: sentinel)
    assert finalizer.optional_judge() is sentinel
