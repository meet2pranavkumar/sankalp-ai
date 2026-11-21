// Dates: the server always speaks UTC. People see and type their own local time.
const pad = (n) => String(n).padStart(2, "0");

/** ISO time from the server -> value for <input type="datetime-local"> in the person's own time zone. */
export function toLocalInput(iso) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Value typed in <input type="datetime-local"> -> ISO time with time zone (UTC) for the server. */
export function fromLocalInput(value) {
  return new Date(value).toISOString();
}

export function formatWhen(iso) {
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

/** 3725000 -> "1:02:05", 65000 -> "01:05", negative -> "00:00" */
export function formatCountdown(ms) {
  if (ms <= 0) return "00:00";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

/** 90 -> "1 h 30 min" */
export function formatMinutes(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}
