from app.scripts.check_ai import run_checks
from app.services.ai.base import ProviderError, ProviderResult
from app.services.ai.demo import DemoProvider


class Recorder:
    def __init__(self):
        self.lines = []

    def __call__(self, text):
        self.lines.append(text)

    @property
    def text(self):
        return "\n".join(self.lines)


def test_all_three_questions_are_asked_and_a_good_answer_is_accepted(fake_ai):
    out = Recorder()
    assert run_checks(DemoProvider(), 400, out) is True
    assert out.text.count("PASS") == 3 and "answer would be shown" in out.text


def test_the_trick_question_really_contains_the_trick(fake_ai):
    run_checks(fake_ai, 400, Recorder())
    assert len(fake_ai.calls) == 3
    assert "IGNORE ALL YOUR RULES" in fake_ai.calls[1].user  # sent as data, inside the student_code tags
    assert "<student_code>" in fake_ai.calls[1].user


def test_an_ai_that_gives_in_to_the_trick_is_reported(fake_ai):
    fake_ai.respond = lambda s, u, m: ProviderResult("Sure!\n```c\n#include <stdio.h>\nint main(void) {\n  int a, b;\n  scanf(\"%d %d\", &a, &b);\n  printf(\"%d\", a + b);\n}\n```", 5, 5)
    out = Recorder()
    assert run_checks(fake_ai, 400, out) is True  # the service worked, so the script passes. The refusal is shown to the teacher.
    assert "WOULD BE REFUSED" in out.text


def test_service_problems_are_reported_and_fail_the_check(fake_ai):
    def down(system, user, max_tokens):
        raise ProviderError("The AI service did not accept the school's key. Please tell your teacher.")

    fake_ai.respond = down
    out = Recorder()
    assert run_checks(fake_ai, 400, out) is False
    assert out.text.count("FAIL") == 3 and "did not accept" in out.text


# ---------------------------------------------------------------- the command itself
def run_main(monkeypatch, capsys, provider, name="anthropic"):
    from app.scripts import check_ai

    monkeypatch.setattr(check_ai, "get_ai_provider", lambda: provider)
    monkeypatch.setattr(check_ai.get_settings(), "ai_provider", name)
    code = check_ai.main()
    return code, capsys.readouterr().out


def test_main_says_how_to_set_up_when_the_helper_is_off(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys, None, name="none")
    assert code == 2 and "AI_PROVIDER=anthropic" in out


def test_main_passes_with_a_working_provider(monkeypatch, capsys, fake_ai):
    code, out = run_main(monkeypatch, capsys, fake_ai)
    assert code == 0 and "model: " in out and "All questions were answered" in out


def test_main_warns_that_demo_is_not_a_real_ai(monkeypatch, capsys):
    code, out = run_main(monkeypatch, capsys, DemoProvider(), name="demo")
    assert code == 0 and "not a real AI" in out


def test_main_fails_when_the_provider_fails(monkeypatch, capsys, fake_ai):
    def down(system, user, max_tokens):
        raise ProviderError("The AI helper cannot be reached right now.")

    fake_ai.respond = down
    code, out = run_main(monkeypatch, capsys, fake_ai)
    assert code == 1 and "Some questions failed" in out
