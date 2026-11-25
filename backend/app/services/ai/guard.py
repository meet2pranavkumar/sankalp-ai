"""Checks every AI answer before a student sees it.

The prompt asks the AI not to give the solution. We do not rely on that. A student can try to trick the AI
(for example by writing 'ignore your rules' inside their code), and AI models make mistakes. So this code
looks at the answer itself and refuses anything that looks like finished code.

It is a set of rules of thumb, not a proof. Every request is also saved, so teachers can see what students were told.
"""
import re

FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
INLINE = re.compile(r"`([^`\n]*)`")

# The shape of a whole program.
PROGRAM = re.compile(
    r"\b(int|void)\s+main\s*\(|static\s+void\s+main|\bdef\s+main\s*\(|if\s+__name__\s*==|\bpublic\s+class\s+\w+"
)

# A "statement" is a piece of text that does something when run. Mentioning a word like `scanf` is fine.
# Writing  print(a + b)  or  total = int(input())  is giving the answer.
IO_CALL = re.compile(r"\b(printf|scanf|print|println|input)\s*\(\s*[^)\s]|\b(cout|cin)\s*(<<|>>)|System\.out\.print")
ASSIGN_CALL = re.compile(r"[\w\])]\s*=\s*[^=\s].*\w\s*\(")  # something = something(...)
TERMINATED = re.compile(r"[\w)\]]\s*;")  # an expression ending with ;
# (plain "else:" or "for each x in the list:" are also normal in pseudo-code, so they are not counted here)
CONTROL = re.compile(r"\b(for|while|if)\s*\(.*\)|\bfor\s+\w+\s+in\s+range\s*\(")

# Lines that look like code in C, C++, Java or Python (used for counting code-looking lines in running text).
CODE_LINE = re.compile(
    r";\s*$|^\s*[{}]\s*$|^\s*(for|while|if|else|elif|def|class|return|import|from)\b.*[:{]\s*$"
    r"|\b(printf|scanf|cout|cin|println|print|input|range|len|int|float|double|char)\s*\("
    r"|\+\+|--|\+=|-=|\*=|==|!=|&&|\|\||\bint\s+\w+\s*=|\bfor\s*\("
)


def statement_like(text: str) -> bool:
    return bool(IO_CALL.search(text) or ASSIGN_CALL.search(text) or TERMINATED.search(text) or CONTROL.search(text))


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _statements_in_text(text_outside_blocks: str) -> tuple[int, int]:
    """(how many statements the text contains, how many lines merely look like code)."""
    statements = like = 0
    for line in _lines(text_outside_blocks):
        for snippet in INLINE.findall(line):  # code hidden between `backticks` still counts
            if statement_like(snippet):
                statements += 1
        bare = INLINE.sub("", line)
        if statement_like(bare):
            statements += 1
        if CODE_LINE.search(bare):
            like += 1
    return statements, like


def _density(block: str) -> float:
    lines = _lines(block)
    return sum(1 for line in lines if CODE_LINE.search(line) or statement_like(line)) / len(lines) if lines else 0.0


def violations(text: str, kind: str, level: int | None = None) -> list[str]:
    """Reasons this answer must not be shown. An empty list means it is fine.

    kind is "hint" or "explain". Level 1 and 2 hints must have no code at all.
    Level 3 may have one short block of pseudo-code. An error explanation may point at the problem with a few lines."""
    reasons: list[str] = []
    no_code_at_all = kind == "hint" and level in (1, 2)
    blocks = FENCE.findall(text)
    outside = FENCE.sub("", text)

    if PROGRAM.search(text):
        reasons.append("it contains the shape of a complete program")

    statements, like = _statements_in_text(outside)
    if statements >= (1 if no_code_at_all else 2):
        reasons.append("it writes code statements in the text")
    if like >= (2 if no_code_at_all else 4):
        reasons.append("it has several lines of code in the text")

    if no_code_at_all:
        if blocks:
            reasons.append("it has a code block in a hint that must not have code")
    elif kind == "hint":  # level 3: pseudo-code
        if len(blocks) > 1:
            reasons.append("it has more than one code block")
        for block in blocks:
            lines = _lines(block)
            if len(lines) > 15:
                reasons.append("the pseudo-code is too long")
            if any(statement_like(line) for line in lines):
                reasons.append("the pseudo-code contains a real code statement")
            elif len(lines) >= 3 and _density(block) >= 0.6:
                reasons.append("the pseudo-code looks like real code")
    else:  # explaining an error
        sizes = [len(_lines(b)) for b in blocks]
        if any(n > 3 for n in sizes) or sum(sizes) > 6:
            reasons.append("it shows too much code for an explanation")
    return reasons
