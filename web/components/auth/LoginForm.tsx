"use client";
import { FormEvent, useState, type CSSProperties } from "react";
import { passwordLogin } from "@/lib/api";

const fieldStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  background: "#16161f",
  border: "1px solid #2a2a38",
  borderRadius: 10,
  padding: "11px 12px",
  fontSize: 14,
  color: "#ececf4",
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
      : oauthError === "oauth"
        ? "Google sign-in didn't complete. Try again."
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
      <p style={{ fontSize: 13, color: "#8a8aa0", lineHeight: 1.5, margin: "0 0 22px" }}>
        Studio is invite-only. Use the invited email and a password, or continue with
        Google. First password sign-in sets that password.
      </p>
      {message && (
        <div
          role="alert"
          style={{
            fontSize: 13,
            color: "#ffd08a",
            background: "#1c1608",
            border: "1px solid #3a2c10",
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
        <label style={{ fontSize: 12, fontWeight: 600, color: "#8a8aa0" }}>
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
        <label style={{ fontSize: 12, fontWeight: 600, color: "#8a8aa0" }}>
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
            background: "#7c5cff",
            border: "none",
            padding: "12px 16px",
            borderRadius: 10,
            cursor: busy ? "wait" : "pointer",
          }}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          margin: "18px 0",
          color: "#5a5a70",
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        <span style={{ flex: 1, height: 1, background: "#23232f" }} />
        or
        <span style={{ flex: 1, height: 1, background: "#23232f" }} />
      </div>
      <a
        href="/api/auth/google/start"
        style={{
          display: "block",
          textAlign: "center",
          textDecoration: "none",
          fontSize: 14,
          fontWeight: 700,
          color: "#ececf4",
          background: "#1b1b27",
          border: "1px solid #2a2a38",
          padding: "12px 16px",
          borderRadius: 10,
        }}
      >
        Continue with Google
      </a>
    </>
  );
}
