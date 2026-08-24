"use client";

import Link from "next/link";
import { ArrowUpDown, CheckSquare, Send } from "lucide-react";

type FilterMode = "all" | "shortfall";
type SortMode = "newest";

interface GalleryToolbarProps {
  count: number;
  variantCount: number;
  filterMode: FilterMode;
  onFilter: (mode: FilterMode) => void;
  sort: SortMode;
  onSort: (sort: SortMode) => void;
  selectedCount: number;
  sendDisabledReason: string | null;
  onSend: () => void;
  selectAllLabel: string;
  selectAllDisabled?: boolean;
  onSelectAll: () => void;
}

export function GalleryToolbar({ count, variantCount, filterMode, onFilter, sort, onSort, selectedCount, sendDisabledReason, onSend, selectAllLabel, selectAllDisabled, onSelectAll }: GalleryToolbarProps) {
  const sendDisabled = sendDisabledReason != null;
  return (
    <section className="gallery-toolbar" aria-label="Gallery controls">
      <div className="gallery-toolbar__count"><b>{count}</b> sources <span>·</span> <b>{variantCount}</b> finished variants</div>
      <div className="gallery-toolbar__actions">
        <div className="gallery-segments" aria-label="Source filter">
          <button type="button" data-active={filterMode === "all"} onClick={() => onFilter("all")}>All sources</button>
          <button type="button" data-active={filterMode === "shortfall"} onClick={() => onFilter("shortfall")}>Needs attention</button>
        </div>
        <Link className="gallery-quiet-link" href="/drops">Sent</Link>
        <Link className="gallery-quiet-link" href="/drops?filter=flagged_week">Flagged</Link>
        <button type="button" className="gallery-quiet-link" onClick={() => onSort("newest")}><ArrowUpDown size={14} /> {sort === "newest" ? "Newest" : "Newest"}</button>
        <button type="button" className="gallery-select-all" onClick={onSelectAll} disabled={selectAllDisabled}><CheckSquare size={14} /> {selectAllLabel}</button>
        <span className="gallery-send-wrap">
          <button type="button" className="vf-primary-button" onClick={onSend} disabled={sendDisabled} title={sendDisabledReason ?? undefined}><Send size={14} /> Send to Drive{selectedCount > 0 ? ` (${selectedCount})` : ""}</button>
          {sendDisabled && <small>{sendDisabledReason}</small>}
        </span>
      </div>
    </section>
  );
}
