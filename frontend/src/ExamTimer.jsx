import { useCountdown } from "./useCountdown.js";
import { formatCountdown } from "./time.js";

/** The big countdown during an exam. It follows the server clock, so changing the computer's clock does not help. */
export default function ExamTimer({ attempt, serverNow, onExpire }) {
  const remaining = useCountdown(attempt.deadline_at, serverNow, onExpire);
  const low = remaining !== null && remaining < 5 * 60 * 1000;
  return (
    <div
      role="timer"
      aria-label="Time left"
      className={`rounded border px-3 py-2 text-sm font-semibold ${low ? "border-red-300 bg-red-50 text-red-800" : "border-amber-300 bg-amber-50 text-amber-900"}`}
    >
      Time left: <span className="font-mono text-base">{formatCountdown(remaining ?? 0)}</span>
    </div>
  );
}
