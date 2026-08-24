import { LoginForm } from "@/components/auth/LoginForm";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const raw = (await searchParams).error;
  const error = Array.isArray(raw) ? raw[0] : raw;

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="login-brand"><span className="login-brand-mark" /> VaryForge</div>
        <h1>Sign in</h1>
        <LoginForm oauthError={error ?? null} />
      </div>
    </main>
  );
}
