// A small bar chart drawn with SVG, so no chart library is needed.
// Each day has a bar for the answers sent (light) with the accepted ones in front (green),
// and a dot at the bottom for every lesson finished.
const W = 600;
const H = 140;
const PAD = 8;

export default function ActivityChart({ days }) {
  const totals = days.reduce(
    (t, d) => ({ submissions: t.submissions + d.submissions, accepted: t.accepted + d.accepted, lessons: t.lessons + d.lessons }),
    { submissions: 0, accepted: 0, lessons: 0 }
  );
  const max = Math.max(1, ...days.map((d) => d.submissions));
  const slot = (W - PAD * 2) / Math.max(1, days.length);
  const barWidth = Math.max(2, slot - 3);
  const usable = H - 34;

  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Activity in the last ${days.length} days: ${totals.submissions} answers and runs, ${totals.accepted} accepted, ${totals.lessons} lessons finished`}
        className="w-full"
      >
        <line x1={PAD} x2={W - PAD} y1={H - 22} y2={H - 22} stroke="#cbd5e1" />
        {days.map((d, i) => {
          const x = PAD + i * slot;
          const total = (d.submissions / max) * usable;
          const good = (d.accepted / max) * usable;
          return (
            <g key={d.date} data-testid="day">
              <title>{`${d.date}: ${d.submissions} answers and runs, ${d.accepted} accepted, ${d.lessons} lessons`}</title>
              {d.submissions > 0 && <rect x={x} y={H - 22 - total} width={barWidth} height={total} rx="2" fill="#c7d2fe" />}
              {d.accepted > 0 && <rect x={x} y={H - 22 - good} width={barWidth} height={good} rx="2" fill="#10b981" />}
              {d.lessons > 0 && <circle cx={x + barWidth / 2} cy={H - 11} r="4" fill="#f59e0b" />}
            </g>
          );
        })}
        {days.length > 0 && (
          <>
            <text x={PAD} y={H - 1} fontSize="10" fill="#64748b">{days[0].date}</text>
            <text x={W - PAD} y={H - 1} fontSize="10" fill="#64748b" textAnchor="end">{days[days.length - 1].date}</text>
          </>
        )}
      </svg>
      <figcaption className="mt-1 flex flex-wrap gap-4 text-xs text-slate-500">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-indigo-200" />answers and runs</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-sm bg-emerald-500" />accepted</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-500" />lesson finished</span>
      </figcaption>
    </figure>
  );
}
