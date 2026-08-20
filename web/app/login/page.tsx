import { LoginForm } from "@/components/auth/LoginForm";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const raw = (await searchParams).error;
  const error = Array.isArray(raw) ? raw[0] : raw;

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
        <LoginForm oauthError={error ?? null} />
      </div>
    </main>
  );
}
