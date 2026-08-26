import { LoginForm } from "@/components/auth/LoginForm";
import { VarimoWordmark } from "@/components/brand/VarimoWordmark";

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
        <div className="login-brand"><VarimoWordmark /></div>
        <h1>Sign in</h1>
        <LoginForm oauthError={error ?? null} />
      </div>
    </main>
  );
}
