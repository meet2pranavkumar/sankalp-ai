import pytest

from app.services.ai.guard import violations

# (name, kind, level, text). The answer must be refused.
BLOCKED = [
    ("L1 code block", "hint", 1, "Try this:\n```\nprint(a+b)\n```"),
    ("L1 unfenced answer line", "hint", 1, "The answer is simple:\nprint(sum(map(int, input().split())))"),
    ("L1 answer in inline backticks", "hint", 1, "Just write `a, b = map(int, input().split())` and then `print(a + b)`."),
    ("L1 answer as one long sentence", "hint", 1, "You can do a = int(input()); b = int(input()); print(a + b) and you are done."),
    ("L1 call in a sentence", "hint", 1, "Simply call print(a + b) at the end."),
    ("L1 c answer in a sentence", "hint", 1, "Write scanf(\"%d %d\", &a, &b); and then printf(\"%d\", a + b);"),
    ("L2 python solution, no fence", "hint", 2, "Here:\na, b = map(int, input().split())\nprint(a + b)"),
    ("L2 solution in tildes fence", "hint", 2, "~~~\na = int(input())\nb = int(input())\nprint(a + b)\n~~~"),
    ("L2 indented code block", "hint", 2, "Do this:\n\n    a = int(input())\n    b = int(input())\n    print(a + b)\n"),
    ("L2 c for loop inline", "hint", 2, "Use `for (int i = 0; i < n; i++)` to repeat."),
    ("L3 real c code", "hint", 3, "```c\nint total = 0;\nfor (int i = 1; i <= n; i++) {\n    total += i;\n}\nprintf(\"%d\", total);\n```"),
    ("L3 two line real python", "hint", 3, "```\na, b = map(int, input().split())\nprint(a + b)\n```"),
    ("L3 one real line", "hint", 3, "```\nprint(sum(map(int, input().split())))\n```"),
    ("L3 python range loop", "hint", 3, "```\ntotal = 0\nfor i in range(n):\n    total += i\n```"),
    ("L3 full c program", "hint", 3, "```\n#include <stdio.h>\nint main(void) {\n  return 0;\n}\n```"),
    ("L3 java class", "hint", 3, "```\npublic class Main {\n}\n```"),
    ("L3 braces and increments, no statements", "hint", 3, "```\n{\n  x++\n}\n```"),
    ("L3 python main", "hint", 3, "```\ndef main():\n    pass\n```"),
    ("L3 too long", "hint", 3, "```\n" + "\n".join(f"step {i}" for i in range(20)) + "\n```"),
    ("L3 two blocks", "hint", 3, "```\nread n\n```\nand then\n```\nprint n\n```"),
    ("L3 code split in inline pieces", "hint", 3, "Write `int a, b;` then `scanf(\"%d %d\", &a, &b);` then `printf(\"%d\", a + b);`"),
    ("explain whole program", "explain", None, "Here is the fixed program:\n```\nint a;\nint b;\nscanf(\"%d\", &a);\nscanf(\"%d\", &b);\nprintf(\"%d\", a+b);\n```"),
    ("explain three blocks, nine lines", "explain", None, "```\na = 1\nb = 2\nc = 3\n```\n```\nd = 4\ne = 5\nf = 6\n```\n```\ng = 7\nh = 8\ni = 9\n```"),
    ("explain one block of four lines", "explain", None, "```\na = 1\nb = 2\nc = 3\nd = 4\n```"),
    ("explain gives main", "explain", None, "Use this: int main(void) { return 0; }"),
]

# Normal, helpful answers that must be shown.
ALLOWED = [
    ("L1 clean question", "hint", 1, "What are the two numbers you must add? Try the sample by hand first."),
    ("L1 asks about the sample", "hint", 1, "Look at the first sample. Which numbers go in, and which number comes out? How could the first become the second?"),
    ("L2 numbered steps", "hint", 2, "1. Read the two numbers.\n2. Add them.\n3. Print the sum."),
    ("L2 names only", "hint", 2, "Use `scanf` to read the numbers, then add them with the `+` operator."),
    ("L2 mentions print()", "hint", 2, "Use the print() function to show the answer."),
    ("L2 prose about ==", "hint", 2, "Remember to use == to compare, not =."),
    ("L2 assignment idea in words", "hint", 2, "Write total = 0 before the loop, then add each number to it."),
    ("L2 loop in words", "hint", 2, "Use a for loop that goes from 1 up to n. Inside it, add the number to your total."),
    ("L3 good pseudo-code", "hint", 3, "```\nread n\nset total to 0\nfor each number from 1 to n:\n    add it to total\nprint total\n```"),
    ("L3 pseudo-code if/else", "hint", 3, "```\nread n\nif n is even:\n    print Even\nelse:\n    print Odd\n```"),
    ("L3 pseudo-code for each", "hint", 3, "```\nfor each number in the list:\n    add it to total\n```"),
    ("explain small fix block", "explain", None, "Line 5 is missing a semicolon at the end:\n```\nprintf(\"hi\");\n```"),
    ("explain inline fix", "explain", None, "Add a semicolon at the end: `printf(\"hi\");`"),
    ("explain plain words", "explain", None, "The compiler says a semicolon is missing. Look at the line before line 5."),
    ("explain include mention", "explain", None, "You forgot `#include <stdio.h>` at the top, so printf is unknown."),
]


@pytest.mark.parametrize("name,kind,level,text", BLOCKED, ids=[c[0] for c in BLOCKED])
def test_answers_that_give_the_solution_are_refused(name, kind, level, text):
    assert violations(text, kind, level), f"should have been refused: {name}"


@pytest.mark.parametrize("name,kind,level,text", ALLOWED, ids=[c[0] for c in ALLOWED])
def test_helpful_answers_are_allowed(name, kind, level, text):
    assert violations(text, kind, level) == [], f"wrongly refused: {name}: {violations(text, kind, level)}"


def test_the_reason_is_given_in_plain_words():
    reasons = violations("```\nprint(1)\n```", "hint", 2)
    assert reasons and all(isinstance(r, str) and r for r in reasons)


def test_empty_answer_has_nothing_wrong_with_it():
    assert violations("", "hint", 1) == []
