import { api } from "./api.js";

// In tests we poll very fast so they finish quickly.
export const POLL_MS = import.meta.env.MODE === "test" ? 5 : 1000;
export const GIVE_UP_MS = 120_000;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Ask the server again and again until the judge has finished. Returns null if the page was left meanwhile. */
export async function waitForResult(submissionId, isAlive = () => true) {
  const started = Date.now();
  while (isAlive()) {
    const sub = await api.getSubmission(submissionId);
    if (sub.status === "done" || sub.status === "error") return sub;
    if (Date.now() - started > GIVE_UP_MS) throw new Error("The judge is taking too long. Please try again.");
    await sleep(POLL_MS);
  }
  return null;
}
