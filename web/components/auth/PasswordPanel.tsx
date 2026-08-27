"use client";
import { FormEvent, useState } from "react";
import { setStudioPassword } from "@/lib/api";
import { useAuthMe } from "@/lib/useAuthMe";

export function PasswordPanel() {
  const { data: me, mutate } = useAuthMe();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!me?.email) return null;
  const hasPassword = Boolean(me.has_password);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await setStudioPassword(password);
      setPassword("");
      setSaved(true);
      await mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        background: "var(--color-panel)",
        border: "1px solid var(--color-line)",
        borderRadius: 14,
        padding: 16,
        marginBottom: 22,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)" }}>
        Studio password
      </div>
      <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 4, lineHeight: 1.45 }}>
        {hasPassword
          ? "Replace the password for email sign-in."
          : "Add a password so you can sign in with email. Drive Connect stays separate."}
      </div>
      <form
        onSubmit={onSubmit}
        style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 12, alignItems: "center" }}
      >
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
          aria-label="New studio password"
          autoComplete="new-password"
          style={{
            background: "var(--color-panel2)",
            border: "1px solid var(--color-line)",
            borderRadius: 9,
            padding: "8px 12px",
            fontSize: 13,
            color: "var(--color-text)",
            minWidth: 220,
            flex: 1,
          }}
        />
        <button
          type="submit"
          disabled={busy}
          className="vf-primary-button"
          style={{ cursor: busy ? "wait" : "pointer" }}
        >
          {busy ? "Saving…" : hasPassword ? "Change password" : "Add password"}
        </button>
      </form>
      {error && (
        <div role="alert" className="vf-alert" style={{ marginTop: 10, marginBottom: 0, fontSize: 12.5 }}>
          {error}
        </div>
      )}
      {saved && (
        <div className="vf-alert vf-alert--ok" style={{ marginTop: 10, marginBottom: 0, fontSize: 12.5 }}>
          Password saved.
        </div>
      )}
    </div>
  );
}
