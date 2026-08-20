"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useDiagnostics } from "@/lib/useDiagnostics";
import { DiagnosticsList } from "@/components/diagnostics/DiagnosticsList";
import { useAuthMe } from "@/lib/useAuthMe";
import { showDiagnosticsNav } from "@/lib/navAccess";

export default function DiagnosticsPage() {
  const router = useRouter();
  const { data: me, isLoading: meLoading } = useAuthMe();
  const allowed = showDiagnosticsNav(me);
  const { data, mutate, isLoading } = useDiagnostics();
  const items = data ?? [];

  useEffect(() => {
    if (meLoading) return;
    if (!allowed) router.replace("/");
  }, [meLoading, allowed, router]);

  if (meLoading || !allowed) {
    return (
      <main style={{ minHeight: "100vh", background: "#0a0a0e" }}>
        <div style={{ padding: "18px 20px", color: "#8a8aa0", fontSize: 13 }}>
          {meLoading ? "Loading…" : "Admin only"}
        </div>
      </main>
    );
  }

  const totalFailed = items.length;

  return (
    <main style={{ minHeight: "100vh" }}>
      {/* Page header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 14,
          padding: "18px 20px 4px",
        }}
      >
        <div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 800,
              color: "var(--color-text)",
            }}
          >
            Diagnostics
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--color-muted)",
              marginTop: 2,
            }}
          >
            {isLoading
              ? "Loading…"
              : totalFailed === 0
              ? "All variants delivered — nothing to report."
              : `${totalFailed} variant${totalFailed !== 1 ? "s" : ""} exhausted the 3-reroll cap. Everything else delivered.`}
          </div>
        </div>
      </div>

      {/* List */}
      <div style={{ padding: "14px 20px 22px" }}>
        {isLoading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "60px 0",
              color: "var(--color-muted)",
              fontSize: 13,
            }}
          >
            Loading diagnostics…
          </div>
        ) : (
          <DiagnosticsList items={items} onRegenerate={() => mutate()} />
        )}
      </div>
    </main>
  );
}
