"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MoreHorizontal, PackageCheck, TriangleAlert } from "lucide-react";
import { listDriveExports } from "@/lib/api";
import { DROPS_EMPTY_COPY, dropStats, filterDropPacks, formatSendDay, parseDropFilter } from "@/lib/drops";
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

function dropTone(pack: DropPack): "pass" | "dupe" | "flag" {
  if (pack.outcome !== "miss") return "pass";
  return pack.miss_labels.includes("duplicate_reject") ? "dupe" : "flag";
}

function pct(n: number | null): string {
  return n === null ? "—" : `${Math.round(n * 100)}%`;
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

  const all = packs ?? [];
  const visible = filterDropPacks(all, mode);
  const allTime = dropStats(all);
  const thisWeek = dropStats(filterDropPacks(all, "week"));

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

      <div className="drops-stats">
        <div className="drops-stat drops-stat--dark">
          <span className="drops-stat__label">Sent · all time</span>
          <strong className="drops-stat__value">{allTime.sent}</strong>
        </div>
        <div className="drops-stat">
          <span className="drops-stat__label">This week</span>
          <strong className="drops-stat__value">{thisWeek.sent}</strong>
        </div>
        <div className="drops-stat">
          <span className="drops-stat__label">Exceptions</span>
          <strong className="drops-stat__value drops-stat__value--exception">{allTime.misses}</strong>
        </div>
        <div className="drops-stat">
          <span className="drops-stat__label">Pass rate</span>
          <strong className="drops-stat__value">{pct(allTime.winRate)}</strong>
        </div>
      </div>

      <div className="drops-filters-row">
        <nav className="drops-filters" aria-label="Drop filters">
          {FILTERS.map((item) => <Link key={item.id} href={item.id === "all" ? "/drops" : `/drops?filter=${item.id}`} data-active={mode === item.id}>{item.label}</Link>)}
        </nav>
        <p className="drops-hint">Unlabeled counts as pass</p>
      </div>

      {error && <p className="drops-error"><TriangleAlert size={15} /> {error}</p>}
      {packs === null && <p className="drops-loading">Loading sent packs…</p>}
      {packs && packs.length === 0 && !error && (
        <div className="workspace-empty"><PackageCheck size={24} /><strong>No drops yet</strong><p>{DROPS_EMPTY_COPY}</p></div>
      )}
      {packs && packs.length > 0 && visible.length === 0 && <div className="workspace-empty"><strong>No drops in this view</strong><p>Try a wider delivery filter.</p></div>}

      {packs && visible.length > 0 && (
        <div className="drops-table" role="table" aria-label="Delivered packs">
          <div className="drops-table__row drops-table__row--head" role="row">
            <span aria-hidden="true" />
            <span role="columnheader">Pack</span>
            <span role="columnheader">Sent</span>
            <span role="columnheader">Files</span>
            <span role="columnheader">Ledger ID</span>
            <span role="columnheader">Result</span>
            <span aria-hidden="true" />
          </div>
          {visible.map((pack) => <DropTableRow key={pack.export_id} pack={pack} />)}
        </div>
      )}
    </section>
  );
}

function DropTableRow({ pack }: { pack: DropPack }) {
  const first = pack.files[0];
  const miss = pack.outcome === "miss";
  const tone = dropTone(pack);
  const href = first ? `/gallery?v=${first.source_id}:${first.index}` : "/gallery";
  const resultLabel = miss ? missLabel(pack.miss_labels) : "Pass";

  return (
    <Link href={href} className="drop-row" role="row" aria-label={`${pack.destination_name}, ${resultLabel}`}>
      <span className="drop-row__dot" data-tone={tone} aria-hidden="true" />
      <span className="drop-row__pack" role="cell">
        <strong>{pack.destination_name}</strong>
        {pack.files.length > 1 && <em>{pack.files.map((file) => file.variant_id).join(" · ")}</em>}
      </span>
      <span className="drop-row__date" role="cell">{formatSendDay(pack.created_utc)}</span>
      <span className="drop-row__files" role="cell">{pack.count} file{pack.count === 1 ? "" : "s"}{first ? ` · ${first.variant_id}` : ""}</span>
      <span className="drop-row__ledger" role="cell" title={pack.export_id}>{pack.export_id}</span>
      <span className="drop-row__result" role="cell" data-tone={tone}>{resultLabel}</span>
      <span className="drop-row__more" aria-hidden="true"><MoreHorizontal size={17} /></span>
    </Link>
  );
}
