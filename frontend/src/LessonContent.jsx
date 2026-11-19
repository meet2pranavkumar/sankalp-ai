import Markdown from "./Markdown.jsx";
import RunnableExample from "./RunnableExample.jsx";
import { splitLesson } from "./lessonBlocks.js";

/** Lesson text with working code examples. An example restarts when the lesson text for it changes (used by the editor preview). */
export default function LessonContent({ markdown }) {
  return (
    <div>
      {splitLesson(markdown).map((part, i) =>
        part.type === "run" ? (
          <RunnableExample key={`${i}-${part.language}-${part.code}-${part.stdin}`} language={part.language} code={part.code} stdin={part.stdin} />
        ) : (
          <Markdown key={i}>{part.text}</Markdown>
        )
      )}
    </div>
  );
}
