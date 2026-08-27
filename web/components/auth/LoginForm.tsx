"use client";
import { FormEvent, useState, type CSSProperties } from "react";
import { passwordLogin } from "@/lib/api";

const fieldStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  background: "#f3f8f9",
  border: "1px solid #c9dde0",
  borderRadius: 10,
  padding: "11px 12px",
  fontSize: 14,
  color: "var(--color-text)",
  outline: "none",
};

export function LoginForm({ oauthError }: { oauthError?: string | null }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const oauthMessage =
    oauthError === "not_invited"
      ? "This email isn't invited. Ask the operator to add you."
      : oauthError
        ? "Use the invited email and your studio password."
        : null;
  const message = error || oauthMessage;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await passwordLogin(email, password);
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <>
      <p style={{ fontSize: 13, color: "var(--color-muted)", lineHeight: 1.5, margin: "0 0 22px" }}>
        Studio is invite-only. Use the invited email and a password.
        First sign-in sets that password.
      </p>
      {message && (
        <div
          role="alert"
          style={{
            fontSize: 13,
            color: "#8e6119",
            background: "#fff8eb",
            border: "1px solid #efdfbd",
            borderRadius: 10,
            padding: "10px 12px",
            marginBottom: 16,
            lineHeight: 1.45,
          }}
        >
          {message}
        </div>
      )}
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: "var(--color-muted)" }}>
          Email
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-label="Email"
            style={{ ...fieldStyle, marginTop: 6 }}
          />
        </label>
        <label style={{ fontSize: 12, fontWeight: 600, color: "var(--color-muted)" }}>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-label="Password"
            style={{ ...fieldStyle, marginTop: 6 }}
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          style={{
            marginTop: 6,
            fontSize: 14,
            fontWeight: 700,
            color: "#fff",
            background: "#172124",
            border: "none",
            padding: "12px 16px",
            borderRadius: 10,
            cursor: busy ? "wait" : "pointer",
          }}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </>
  );
}
