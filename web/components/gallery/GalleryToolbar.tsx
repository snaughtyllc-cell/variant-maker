"use client";

import Link from "next/link";
import { ArrowUpDown, CheckSquare } from "lucide-react";

type FilterMode = "all" | "shortfall";
type SortMode = "newest";

interface GalleryToolbarProps {
  count: number;
  variantCount: number;
  filterMode: FilterMode;
  onFilter: (mode: FilterMode) => void;
  sort: SortMode;
  onSort: (sort: SortMode) => void;
  selectAllLabel: string;
  selectAllDisabled?: boolean;
  onSelectAll: () => void;
}

export function GalleryToolbar({
  count,
  variantCount,
  filterMode,
  onFilter,
  sort,
  onSort,
  selectAllLabel,
  selectAllDisabled,
  onSelectAll,
}: GalleryToolbarProps) {
  return (
    <section className="gallery-toolbar" aria-label="Gallery controls">
      <div className="gallery-toolbar__count"><b>{count}</b> sources <span>·</span> <b>{variantCount}</b> finished variants</div>
      <div className="gallery-toolbar__actions">
        <div className="gallery-segments" aria-label="Source filter">
          <button type="button" data-active={filterMode === "all"} onClick={() => onFilter("all")}>All sources</button>
          <button type="button" data-active={filterMode === "shortfall"} onClick={() => onFilter("shortfall")}>Needs attention</button>
        </div>
        <Link className="gallery-quiet-link" href="/drops" aria-label="Sent to Drive">Sent</Link>
        <Link className="gallery-quiet-link" href="/drops?filter=flagged_week" aria-label="Flagged this week">Flagged</Link>
        <button type="button" className="gallery-quiet-link" onClick={() => onSort("newest")}><ArrowUpDown size={14} /> {sort === "newest" ? "Newest" : "Newest"}</button>
        <button type="button" className="gallery-select-all" onClick={onSelectAll} disabled={selectAllDisabled}><CheckSquare size={14} /> {selectAllLabel}</button>
      </div>
    </section>
  );
}
