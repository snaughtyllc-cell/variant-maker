"use client";
import Link from "next/link";

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

export function GalleryToolbar({
  count,
  variantCount,
  filterMode,
  onFilter,
  sort,
  onSort,
  selectedCount,
  sendDisabledReason,
  onSend,
  selectAllLabel,
  selectAllDisabled,
  onSelectAll,
}: GalleryToolbarProps) {
  const sendDisabled = sendDisabledReason != null;
  const chipBase: React.CSSProperties = {
    fontSize: 12,
    color: "var(--color-muted)",
    background: "#14141d",
    border: "1px solid var(--color-line)",
    padding: "10px 11px",
    borderRadius: 8,
    cursor: "pointer",
    userSelect: "none",
  };

  const chipOn: React.CSSProperties = {
    ...chipBase,
    color: "#fff",
    borderColor: "#2f2a52",
    background: "#191527",
  };

  return (
    <div className="gallery-toolbar">
      <div style={{ fontSize: 12.5, color: "var(--color-muted)" }}>
        <b style={{ color: "var(--color-text)" }}>{count}</b> sources ·{" "}
        <b style={{ color: "var(--color-text)" }}>{variantCount}</b> variants delivered
      </div>
      <div className="gallery-toolbar__actions">
        <span
          style={filterMode === "all" ? chipOn : chipBase}
          onClick={() => onFilter("all")}
        >
          All sources
        </span>
        <span
          style={filterMode === "shortfall" ? chipOn : chipBase}
          onClick={() => onFilter("shortfall")}
        >
          Has shortfall
        </span>
        <Link href="/drops" style={{ ...chipBase, textDecoration: "none" }}>
          Sent to Drive
        </Link>
        <Link href="/drops?filter=flagged_week" style={{ ...chipBase, textDecoration: "none" }}>
          Flagged this week
        </Link>
        <span
          style={chipBase}
          onClick={() => onSort("newest")}
        >
          Sort: {sort === "newest" ? "Newest" : "Newest"} ▾
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={onSelectAll}
            disabled={selectAllDisabled}
            style={{
              ...chipBase,
              minHeight: 44,
              fontWeight: 700,
              opacity: selectAllDisabled ? 0.5 : 1,
              cursor: selectAllDisabled ? "not-allowed" : "pointer",
            }}
          >
            {selectAllLabel}
          </button>
          <button
            onClick={onSend}
            disabled={sendDisabled}
            title={sendDisabledReason ?? undefined}
            style={{
              fontSize: 12,
              fontWeight: 700,
              color: "#fff",
              background: sendDisabled ? "#3a2c5c" : "linear-gradient(135deg, #7c5cff, #ff4d8d)",
              border: "none",
              padding: "10px 14px",
              minHeight: 44,
              borderRadius: 8,
              cursor: sendDisabled ? "not-allowed" : "pointer",
              opacity: sendDisabled ? 0.6 : 1,
            }}
          >
            ⇪ Send to Drive{selectedCount > 0 ? ` (${selectedCount})` : ""}
          </button>
          {sendDisabled && (
            <span style={{ fontSize: 11, color: "var(--color-muted)" }}>{sendDisabledReason}</span>
          )}
        </div>
      </div>
    </div>
  );
}
