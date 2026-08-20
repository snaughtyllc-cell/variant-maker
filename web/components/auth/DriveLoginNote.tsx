"use client";
import { useAuthMe } from "@/lib/useAuthMe";

export function DriveLoginNote() {
  const { data } = useAuthMe();
  if (!data?.email) return null;
  return (
    <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 6, lineHeight: 1.45 }}>
      Drive Connect is per workspace and separate from Studio login. Connect
      Google, then add a destination folder — Workflows and Send to Drive use it.
    </div>
  );
}
