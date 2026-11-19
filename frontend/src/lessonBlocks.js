// Finds the code examples that have a Run button inside a lesson.
//   ```c run      <- a runnable example
//   ```stdin      <- (optional, directly after it) the example's default input
// The backend does the same in backend/app/seed/blocks.py. Keep the two in step.
const FENCE = /^```([A-Za-z0-9_+-]+)([^\n]*)\n([\s\S]*?)^```[ \t]*$/gm;
export const RUNNABLE_LANGUAGES = new Set(["c", "cpp", "java", "python"]);

const trimEnd = (text) => text.replace(/\n$/, "");

/** Splits lesson text into plain Markdown parts and runnable examples, in order. */
export function splitLesson(markdown) {
  const matches = [...markdown.matchAll(FENCE)];
  const parts = [];
  const attached = new Set();
  let cursor = 0;
  // Blank space between two examples is not text. Skipping it avoids empty boxes on the page.
  const addText = (text) => {
    if (text.trim() !== "") parts.push({ type: "markdown", text });
  };

  matches.forEach((m, i) => {
    if (attached.has(i)) return;
    const language = m[1].toLowerCase();
    const flags = m[2].trim().split(/\s+/);
    if (!RUNNABLE_LANGUAGES.has(language) || !flags.includes("run")) return;

    let end = m.index + m[0].length;
    let stdin = "";
    const next = matches[i + 1];
    if (next && next[1].toLowerCase() === "stdin" && markdown.slice(end, next.index).trim() === "") {
      stdin = trimEnd(next[3]);
      end = next.index + next[0].length;
      attached.add(i + 1);
    }
    addText(markdown.slice(cursor, m.index));
    parts.push({ type: "run", language, code: trimEnd(m[3]), stdin });
    cursor = end;
  });

  addText(markdown.slice(cursor));
  return parts;
}
