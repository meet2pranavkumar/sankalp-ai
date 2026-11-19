import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Plain Markdown with tables. Raw HTML in the text is NOT allowed (react-markdown ignores it), so lessons are safe.
const STYLE =
  "space-y-3 text-sm leading-relaxed text-slate-800 " +
  "[&_h1]:text-xl [&_h1]:font-bold [&_h2]:mt-5 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:font-semibold " +
  "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 " +
  "[&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:font-mono [&_code]:text-[0.85em] " +
  "[&_pre]:overflow-auto [&_pre]:rounded [&_pre]:bg-slate-100 [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 " +
  "[&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-slate-300 [&_th]:bg-slate-50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left " +
  "[&_td]:border [&_td]:border-slate-300 [&_td]:px-2 [&_td]:py-1 " +
  "[&_blockquote]:border-l-4 [&_blockquote]:border-indigo-300 [&_blockquote]:bg-indigo-50 [&_blockquote]:px-3 [&_blockquote]:py-2 " +
  "[&_a]:text-indigo-700 [&_a]:underline";

export default function Markdown({ children }) {
  return (
    <div className={STYLE}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
