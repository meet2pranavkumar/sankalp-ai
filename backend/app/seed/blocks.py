"""Runnable code examples inside lesson text.

In a lesson, a code block whose first line is  ```c run  gets a Run button for the student.
A block   ```stdin   right after it gives the example's default input.
The website does the same parsing in frontend/src/lessonBlocks.js. Keep the two in step.
"""
import re
from dataclasses import dataclass

RUNNABLE_LANGUAGES = {"c", "cpp", "java", "python"}
FENCE = re.compile(r"^```([A-Za-z0-9_+-]+)([^\n]*)\n(.*?)^```[ \t]*$", re.S | re.M)


@dataclass
class Runnable:
    language: str
    code: str
    stdin: str = ""


def extract_runnables(markdown: str) -> list[Runnable]:
    found: list[Runnable] = []
    matches = list(FENCE.finditer(markdown))
    skip: set[int] = set()
    for i, m in enumerate(matches):
        if i in skip:
            continue
        language, meta, body = m.group(1).lower(), m.group(2).split(), m.group(3)
        if language not in RUNNABLE_LANGUAGES or "run" not in meta:
            continue
        stdin = ""
        if i + 1 < len(matches):
            nxt = matches[i + 1]
            between = markdown[m.end() : nxt.start()]
            if nxt.group(1).lower() == "stdin" and between.strip() == "":
                stdin = nxt.group(3)
                skip.add(i + 1)
        found.append(Runnable(language, body, stdin))
    return found
