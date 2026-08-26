import { LoginForm } from "@/components/auth/LoginForm";
import { VarimoMark } from "@/components/brand/VarimoMark";

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
        <div className="login-brand"><VarimoMark className="login-brand-mark" size={18} /> varimo</div>
        <h1>Sign in</h1>
        <LoginForm oauthError={error ?? null} />
      </div>
    </main>
  );
}
