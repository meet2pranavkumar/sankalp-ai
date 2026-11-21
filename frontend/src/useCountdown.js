import { useEffect, useMemo, useRef, useState } from "react";

const TICK_MS = import.meta.env.MODE === "test" ? 20 : 1000;

/**
 * Milliseconds left until `deadlineIso`, counted with the SERVER's clock.
 * The browser clock can be wrong (or changed by the student), so we measure how far it is
 * from the server clock once, when the page loads, and correct for it.
 * `onExpire` is called once when the time reaches zero.
 */
export function useCountdown(deadlineIso, serverNowIso, onExpire) {
  const deadline = deadlineIso ? new Date(deadlineIso).getTime() : null;
  const offset = useMemo(
    () => (serverNowIso ? new Date(serverNowIso).getTime() - Date.now() : 0),
    [serverNowIso, deadlineIso] // eslint-disable-line react-hooks/exhaustive-deps
  );
  const left = () => (deadline === null ? null : deadline - (Date.now() + offset));
  const [remaining, setRemaining] = useState(left);
  const fired = useRef(false);
  const callback = useRef(onExpire);
  callback.current = onExpire;

  useEffect(() => {
    fired.current = false;
    setRemaining(left());
    if (deadline === null) return undefined;
    const timer = setInterval(() => {
      const value = left();
      setRemaining(value);
      if (value <= 0 && !fired.current) {
        fired.current = true;
        callback.current?.();
      }
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [deadline, offset]); // eslint-disable-line react-hooks/exhaustive-deps

  return remaining;
}
