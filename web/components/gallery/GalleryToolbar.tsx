"use client";

type FilterMode = "all" | "shortfall";
type SortMode = "newest";

interface GalleryToolbarProps {
  count: number;
  variantCount: number;
  filterMode: FilterMode;
  onFilter: (mode: FilterMode) => void;
  sort: SortMode;
  onSort: (sort: SortMode) => void;
}

export function GalleryToolbar({
  count,
  variantCount,
  filterMode,
  onFilter,
  sort,
  onSort,
}: GalleryToolbarProps) {
  const chipBase: React.CSSProperties = {
    fontSize: 12,
    color: "var(--color-muted)",
    background: "#14141d",
    border: "1px solid var(--color-line)",
    padding: "6px 11px",
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
    <div
      style={{
        display: "flex",
        alignItems: "center",
        padding: "16px 20px 6px",
        gap: 14,
      }}
    >
      <div style={{ fontSize: 12.5, color: "var(--color-muted)" }}>
        <b style={{ color: "var(--color-text)" }}>{count}</b> sources ·{" "}
        <b style={{ color: "var(--color-text)" }}>{variantCount}</b> variants delivered
      </div>
      <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
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
        <span
          style={chipBase}
          onClick={() => onSort("newest")}
        >
          Sort: {sort === "newest" ? "Newest" : "Newest"} ▾
        </span>
      </div>
    </div>
  );
}
