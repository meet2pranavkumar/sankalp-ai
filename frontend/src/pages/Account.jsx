import { useState } from "react";
import { api } from "../api.js";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

export default function Account() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setMessage(null);
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      setMessage({ kind: "ok", text: "Password changed." });
    } catch (err) {
      setMessage({ kind: "error", text: err.message });
    }
  }

  return (
    <Card title="Change my password" className="max-w-md">
      <form onSubmit={submit} className="space-y-3">
        <Field label="Current password">
          <input type="password" required className={inputClass} value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password (at least 8 characters)">
          <input type="password" required minLength={8} className={inputClass} value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        {message && <Alert kind={message.kind}>{message.text}</Alert>}
        <Button type="submit">Change password</Button>
      </form>
    </Card>
  );
}
