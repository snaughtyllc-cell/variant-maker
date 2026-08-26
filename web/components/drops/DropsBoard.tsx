"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, PackageCheck, TriangleAlert } from "lucide-react";
import { listDriveExports } from "@/lib/api";
import { DROPS_EMPTY_COPY, filterDropPacks, formatSendDay, parseDropFilter, winRateCopy } from "@/lib/drops";
import type { DropFilter, DropPack } from "@/lib/types";

const FILTERS: { id: DropFilter; label: string }[] = [
  { id: "all", label: "All sent" },
  { id: "week", label: "This week" },
  { id: "misses", label: "Misses only" },
  { id: "flagged_week", label: "Flagged this week" },
];

function missLabel(labels: string[]): string {
  if (labels.includes("flagged") && labels.includes("duplicate_reject")) return "Flagged + duplicate";
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
      .then((rows) => { setPacks(rows); setError(null); })
      .catch((reason: unknown) => { setError(reason instanceof Error ? reason.message : "Could not load drops"); setPacks([]); });
  }, []);

  const visible = filterDropPacks(packs ?? [], mode);

  return (
    <section className="workspace-page-shell drops-board">
      <header className="workspace-heading">
        <span className="workspace-heading__icon"><PackageCheck size={19} /></span>
        <div>
          <p className="workspace-heading__eyebrow">Delivery record</p>
          <h1>Drops</h1>
          <p className="workspace-heading__copy">Drive-sent packs for the week. Unlabeled is a pass; flagged or duplicate rejected is a miss worth reviewing.</p>
        </div>
      </header>

      <nav className="drops-filters" aria-label="Drop filters">
        {FILTERS.map((item) => <Link key={item.id} href={item.id === "all" ? "/drops" : `/drops?filter=${item.id}`} data-active={mode === item.id}>{item.label}</Link>)}
      </nav>

      {packs && packs.length > 0 && visible.length > 0 && <p className="drops-summary">{winRateCopy(visible)}</p>}
      {error && <p className="drops-error"><TriangleAlert size={15} /> {error}</p>}
      {packs === null && <p className="drops-loading">Loading sent packs…</p>}
      {packs && packs.length === 0 && !error && (
        <div className="workspace-empty"><PackageCheck size={24} /><strong>No drops yet</strong><p>{DROPS_EMPTY_COPY}</p></div>
      )}
      {packs && packs.length > 0 && visible.length === 0 && <div className="workspace-empty"><strong>No drops in this view</strong><p>Try a wider delivery filter.</p></div>}
      <div className="drops-list">{visible.map((pack) => <DropPackRow key={pack.export_id} pack={pack} />)}</div>
    </section>
  );
}

function DropPackRow({ pack }: { pack: DropPack }) {
  const first = pack.files[0];
  const miss = pack.outcome === "miss";
  const href = first ? `/gallery?v=${first.source_id}:${first.index}` : "/gallery";
  return (
    <Link href={href} className="drop-row">
      <span className="drop-row__icon" data-miss={miss}>{miss ? <TriangleAlert size={18} /> : <CheckCircle2 size={18} />}</span>
      <span className="drop-row__main">
        <strong>{pack.destination_name}</strong>
        <small>{formatSendDay(pack.created_utc)} · {pack.count} file{pack.count === 1 ? "" : "s"}{first ? ` · ${first.variant_id}` : ""}</small>
        {pack.files.length > 1 && <em>{pack.files.map((file) => file.variant_id).join(" · ")}</em>}
      </span>
      <span className="drop-row__outcome" data-miss={miss}>{miss ? missLabel(pack.miss_labels) : "Pass"}</span>
    </Link>
  );
}
