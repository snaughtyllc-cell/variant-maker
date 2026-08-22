"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { listDriveExports } from "@/lib/api";
import {
  DROPS_EMPTY_COPY,
  filterDropPacks,
  formatSendDay,
  parseDropFilter,
  winRateCopy,
} from "@/lib/drops";
import type { DropFilter, DropPack } from "@/lib/types";

const FILTERS: { id: DropFilter; label: string }[] = [
  { id: "all", label: "All sent" },
  { id: "week", label: "This week" },
  { id: "misses", label: "Misses only" },
  { id: "flagged_week", label: "Flagged this week" },
];

function missLabel(labels: string[]): string {
  if (labels.includes("flagged") && labels.includes("duplicate_reject")) {
    return "Flagged + duplicate";
  }
  if (labels.includes("duplicate_reject")) return "Duplicate rejected";
  if (labels.includes("flagged")) return "Flagged";
  return "Miss";
}

export function DropsBoard({ filter }: { filter: string | null }) {
  const mode = parseDropFilter(filter);
  const [packs, setPacks] = useState<DropPack[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDriveExports()
      .then((rows) => {
        setPacks(rows);
        setError(null);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Could not load drops");
        setPacks([]);
      });
  }, []);

  const visible = filterDropPacks(packs ?? [], mode);
  const chipBase: React.CSSProperties = {
    fontSize: 12,
    color: "var(--color-muted)",
    background: "#14141d",
    border: "1px solid var(--color-line)",
    padding: "10px 11px",
    borderRadius: 8,
    cursor: "pointer",
    userSelect: "none",
    textDecoration: "none",
  };
  const chipOn: React.CSSProperties = {
    ...chipBase,
    color: "#fff",
    borderColor: "#2f2a52",
    background: "#191527",
  };

  return (
    <div style={{ padding: "18px 20px 32px", maxWidth: 860 }}>
      <div style={{ fontSize: 16, fontWeight: 800, color: "var(--color-text)" }}>Drops</div>
      <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 4, marginBottom: 14 }}>
        Drive-sent packs. Unlabeled is a pass. Flagged / duplicate rejected is a miss.
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
        {FILTERS.map((f) => (
          <Link
            key={f.id}
            href={f.id === "all" ? "/drops" : `/drops?filter=${f.id}`}
            style={mode === f.id ? chipOn : chipBase}
          >
            {f.label}
          </Link>
        ))}
      </div>
      {packs && packs.length > 0 && visible.length > 0 && (
        <div style={{ fontSize: 12.5, color: "var(--color-muted)", marginBottom: 16 }}>
          {winRateCopy(visible)}
        </div>
      )}
      {error && (
        <div style={{ fontSize: 13, color: "var(--color-red)", marginBottom: 12 }}>{error}</div>
      )}
      {packs === null && (
        <div style={{ fontSize: 13, color: "var(--color-muted)", padding: "40px 0" }}>
          Loading drops…
        </div>
      )}
      {packs && packs.length === 0 && !error && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "80px 0",
            color: "var(--color-muted)",
            textAlign: "center",
            gap: 12,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--color-text)", opacity: 0.6 }}>
            {DROPS_EMPTY_COPY}
          </div>
        </div>
      )}
      {packs && packs.length > 0 && visible.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--color-muted)", padding: "24px 0" }}>
          No drops in this filter.
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {visible.map((pack) => (
          <DropPackRow key={pack.export_id} pack={pack} />
        ))}
      </div>
    </div>
  );
}

function DropPackRow({ pack }: { pack: DropPack }) {
  const first = pack.files[0];
  const href = first ? `/gallery?v=${first.source_id}:${first.index}` : "/gallery";
  const miss = pack.outcome === "miss";
  return (
    <Link
      href={href}
      style={{
        display: "block",
        textDecoration: "none",
        color: "inherit",
        background: "#101018",
        border: "1px solid var(--color-line)",
        borderRadius: 12,
        padding: "12px 14px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-text)" }}>
            {pack.destination_name}
          </div>
          <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 3 }}>
            {formatSendDay(pack.created_utc)} · {pack.count} file{pack.count === 1 ? "" : "s"}
            {first ? ` · ${first.variant_id}` : ""}
            {first?.job_id ? ` · ${first.job_id}` : ""}
          </div>
        </div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 800,
            alignSelf: "flex-start",
            padding: "4px 8px",
            borderRadius: 7,
            background: miss ? "#2c1018" : "#0c2c1a",
            color: miss ? "#ff9aa8" : "#7bf2a8",
            border: `1px solid ${miss ? "#5a1a28" : "#16502f"}`,
          }}
        >
          {miss ? missLabel(pack.miss_labels) : "Pass"}
        </span>
      </div>
      {pack.files.length > 1 && (
        <div style={{ fontSize: 11.5, color: "var(--color-muted)", marginTop: 8 }}>
          {pack.files.map((f) => f.variant_id).join(" · ")}
        </div>
      )}
    </Link>
  );
}
