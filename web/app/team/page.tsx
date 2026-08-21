"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createWorkspaceInvite,
  deleteWorkspaceInvite,
  getWorkspaceTeam,
  removeWorkspaceMember,
} from "@/lib/api";
import { useAuthMe } from "@/lib/useAuthMe";
import type { Team } from "@/lib/types";

function canManageTeam(role: string | null | undefined, isAdmin: boolean | undefined): boolean {
  return role === "owner" || Boolean(isAdmin);
}

export default function TeamPage() {
  const router = useRouter();
  const { data: me, isLoading: meLoading } = useAuthMe();
  const allowed = canManageTeam(me?.role, me?.is_admin);
  const [team, setTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [removingEmail, setRemovingEmail] = useState<string | null>(null);

  useEffect(() => {
    if (meLoading) return;
    if (!allowed) {
      router.replace("/");
    }
  }, [meLoading, allowed, router]);

  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const next = await getWorkspaceTeam();
        if (!cancelled) setTeam(next);
      } catch (err) {
        if (!cancelled) {
          setFormError(err instanceof Error ? err.message : "Failed to load team");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [allowed]);

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await createWorkspaceInvite(email.trim());
      setTeam((prev) =>
        prev
          ? { ...prev, invites: [created, ...prev.invites.filter((i) => i.email !== created.email)] }
          : prev,
      );
      setEmail("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create invite");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemoveUser(memberEmail: string) {
    if (removingEmail) return;
    const ok = window.confirm(
      `Remove ${memberEmail}? They will not be able to sign in until you invite them again.`,
    );
    if (!ok) return;
    setRemovingEmail(memberEmail);
    setFormError(null);
    try {
      await removeWorkspaceMember(memberEmail);
      const next = await getWorkspaceTeam();
      setTeam(next);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to remove member");
    } finally {
      setRemovingEmail(null);
    }
  }

  async function handleDeleteInvite(id: string) {
    try {
      await deleteWorkspaceInvite(id);
      setTeam((prev) =>
        prev ? { ...prev, invites: prev.invites.filter((inv) => inv.id !== id) } : prev,
      );
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to delete invite");
    }
  }

  if (meLoading || !allowed) {
    return (
      <main style={{ minHeight: "100vh", background: "#0a0a0e" }}>
        <div style={{ padding: "18px 20px", color: "#8a8aa0", fontSize: 13 }}>
          {meLoading ? "Loading…" : "Owner only"}
        </div>
      </main>
    );
  }

  const studioName = team?.workspace_name || me?.workspace_name || "this studio";

  return (
    <main style={{ minHeight: "100vh" }}>
      <div style={{ padding: "18px 20px 4px" }}>
        <div style={{ fontSize: 16, fontWeight: 800, color: "var(--color-text)" }}>Team</div>
        <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2, maxWidth: 560, lineHeight: 1.45 }}>
          Invite VAs here — they join{" "}
          <strong style={{ color: "var(--color-text)", fontWeight: 700 }}>{studioName}</strong>
          {" "}(gallery, captions, Drive), not a new empty studio. Daily packs are
          Generate Fast (CPU). The small Gallery tile % is uniqueness (~38% floor).
          HQ is reconstructive GPU — slower, not the daily 20.
        </div>
      </div>

      <div style={{ padding: "14px 20px 22px" }}>
        {me?.viewing_other && (
          <div
            role="status"
            style={{
              marginBottom: 16,
              padding: "10px 12px",
              background: "#1a1610",
              border: "1px solid #3a3020",
              borderRadius: 10,
              color: "#ffd08a",
              fontSize: 13,
              lineHeight: 1.45,
            }}
          >
            Team always manages your home studio, not the one in the Viewing banner.
          </div>
        )}
        {formError && (
          <div
            role="alert"
            style={{
              marginBottom: 16,
              padding: "10px 12px",
              background: "#1c1608",
              border: "1px solid #3a2c10",
              borderRadius: 10,
              color: "#ffd08a",
              fontSize: 13,
            }}
          >
            {formError}
          </div>
        )}

        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", marginBottom: 10 }}>
          Members
        </div>
        <div
          style={{
            background: "var(--color-panel)",
            border: "1px solid var(--color-line)",
            borderRadius: 14,
            marginBottom: 28,
            overflow: "hidden",
          }}
        >
          {loading && !team ? (
            <div style={{ padding: 14, fontSize: 12.5, color: "var(--color-muted)" }}>Loading…</div>
          ) : (team?.members ?? []).length === 0 ? (
            <div style={{ padding: 14, fontSize: 12.5, color: "var(--color-muted)" }}>
              No members yet. Invite VAs here — they join this studio, then Generate Fast 20 and Send to Drive.
            </div>
          ) : (
            (team?.members ?? []).map((m) => {
              const isYou = m.email === me?.email;
              return (
                <div
                  key={m.email}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 14px",
                    borderBottom: "1px solid var(--color-line)",
                    fontSize: 12.5,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700 }}>{m.email}</div>
                    <div style={{ color: "var(--color-muted)", marginTop: 2 }}>
                      {m.role}
                      {isYou ? " · you" : ""}
                    </div>
                  </div>
                  {!isYou && (
                    <button
                      type="button"
                      onClick={() => handleRemoveUser(m.email)}
                      disabled={removingEmail === m.email}
                      aria-label={`Remove ${m.email}`}
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--color-red)",
                        background: "var(--color-panel2)",
                        border: "1px solid var(--color-line)",
                        padding: "7px 12px",
                        borderRadius: 9,
                        cursor: removingEmail === m.email ? "wait" : "pointer",
                      }}
                    >
                      {removingEmail === m.email ? "Removing…" : "Remove"}
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)", marginBottom: 10 }}>
          Invite a VA
        </div>
        <form
          onSubmit={handleInvite}
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            alignItems: "center",
            marginBottom: 12,
          }}
        >
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="va@example.com"
            aria-label="Invite email"
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
            disabled={submitting}
            style={{
              fontSize: 12.5,
              fontWeight: 700,
              color: "#fff",
              background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
              border: "none",
              padding: "8px 14px",
              borderRadius: 9,
              cursor: submitting ? "wait" : "pointer",
            }}
          >
            {submitting ? "Sending…" : "Invite"}
          </button>
        </form>
        <div style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 12, lineHeight: 1.45 }}>
          They sign in at this Studio URL with that email plus a password they choose, or with Google.
          First password sign-in sets it. This is a join invite — they land in your studio, not a new one.
          Tell them: Generate Fast 20, read uniqueness on the tile %, Send to Drive.
          Yellow “fell short after auto-retry” is VMAF, not uniqueness.
        </div>

        <div
          style={{
            background: "var(--color-panel)",
            border: "1px solid var(--color-line)",
            borderRadius: 14,
            overflow: "hidden",
          }}
        >
          {(team?.invites ?? []).length === 0 ? (
            <div style={{ padding: 14, fontSize: 12.5, color: "var(--color-muted)" }}>No pending invites.</div>
          ) : (
            (team?.invites ?? []).map((inv) => (
              <div
                key={inv.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--color-line)",
                  fontSize: 12.5,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700 }}>{inv.email}</div>
                  <div style={{ color: "var(--color-muted)", marginTop: 2 }}>
                    Join this workspace
                    {inv.created_utc ? ` · ${inv.created_utc.replace("T", " ").replace("Z", "")}` : ""}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteInvite(inv.id)}
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--color-red)",
                    background: "var(--color-panel2)",
                    border: "1px solid var(--color-line)",
                    padding: "7px 12px",
                    borderRadius: 9,
                    cursor: "pointer",
                  }}
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
