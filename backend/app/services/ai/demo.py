"""Fixed example hints, with no AI. For trying the screens before you have an API key.
These are NOT written for the student's code. They are the same for every problem."""
import re

from app.services.ai.base import ProviderResult

NOTE = "(Demo helper: this is an example hint, not written for your code.)"

HINTS = {
    1: "Read the problem again slowly. What is the input? What must the output be? "
       "Try the first sample by hand, one step at a time, and write down each step you take.",
    2: "Think about the method. Which values do you need to read? Do you need a condition (if) or a loop? "
       "Write the steps in plain words first: 1) read the input, 2) work out the answer step by step, 3) print it.",
    3: "```\nread the input values\nset a result variable to a starting value\n"
       "repeat for each value:\n    update the result using the value\nprint the result\n```\n"
       "Now decide what the starting value is and how the result is updated.",
}
EXPLAIN = (
    "The error message names a line number. Look at that line, and also at the line just before it. "
    "Common causes: a missing semicolon, a missing bracket, a word spelled wrongly, or a variable used before it was created."
)


class DemoProvider:
    def complete(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        if "Task: explain error" in user:
            return ProviderResult(f"{EXPLAIN}\n\n{NOTE}", 0, 0)
        match = re.search(r"Hint level: (\d)", user)
        level = int(match.group(1)) if match else 1
        return ProviderResult(f"{HINTS.get(level, HINTS[1])}\n\n{NOTE}", 0, 0)
