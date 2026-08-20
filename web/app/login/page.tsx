export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const raw = (await searchParams).error;
  const error = Array.isArray(raw) ? raw[0] : raw;
  const message =
    error === "not_invited"
      ? "This Google account isn't invited. Ask the operator to add you."
      : error === "oauth"
        ? "Google sign-in didn't complete. Try again."
        : null;

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0a0a0e",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 400,
          background: "#101018",
          border: "1px solid #23232f",
          borderRadius: 16,
          padding: "32px 28px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <span
            style={{
              width: 18,
              height: 18,
              borderRadius: 6,
              display: "inline-block",
              background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
              boxShadow: "0 0 12px #7c5cff66",
            }}
          />
          <span style={{ fontWeight: 800, fontSize: 16, color: "#ececf4" }}>VaryForge</span>
        </div>
        <div style={{ fontSize: 20, fontWeight: 800, color: "#ececf4", marginBottom: 8 }}>
          Sign in
        </div>
        <p style={{ fontSize: 13, color: "#8a8aa0", lineHeight: 1.5, margin: "0 0 22px" }}>
          Studio is invite-only. Ask the operator for access, then continue with Google.
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
        <a
          href="/api/auth/google/start"
          style={{
            display: "block",
            textAlign: "center",
            textDecoration: "none",
            fontSize: 14,
            fontWeight: 700,
            color: "#fff",
            background: "#7c5cff",
            padding: "12px 16px",
            borderRadius: 10,
          }}
        >
          Continue with Google
        </a>
      </div>
    </main>
  );
}
