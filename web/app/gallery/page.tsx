"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useGallery } from "@/lib/useGallery";
import { useRun } from "@/lib/runStore";
import { filterSources, sortSources } from "@/lib/gallery";
import { GalleryToolbar } from "@/components/gallery/GalleryToolbar";
import { SourceGroup } from "@/components/gallery/SourceGroup";
import { VariantSheet } from "@/components/variant/VariantSheet";

type FilterMode = "all" | "shortfall";
type SortMode = "newest";

function GalleryContent() {
  const { data: sources, mutate, isLoading } = useGallery();
  const { complete } = useRun();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [sort, setSort] = useState<SortMode>("newest");

  // Revalidate gallery when active run completes
  useEffect(() => {
    if (complete) {
      mutate();
    }
  }, [complete, mutate]);

  // Parse ?v=<source_id>:<index>
  const vParam = searchParams.get("v");
  let sheetSourceId: string | null = null;
  let sheetIndex: number | null = null;

  if (vParam) {
    const colonIdx = vParam.lastIndexOf(":");
    if (colonIdx > 0) {
      sheetSourceId = vParam.slice(0, colonIdx);
      const idxStr = vParam.slice(colonIdx + 1);
      const parsed = parseInt(idxStr, 10);
      if (!isNaN(parsed)) sheetIndex = parsed;
    }
  }

  // Resolve source for the sheet
  const allSources = sources ?? [];
  const sheetSource = sheetSourceId
    ? allSources.find((s) => s.source_id === sheetSourceId)
    : undefined;

  // Resolve variant.index (1-based) to array position via findIndex
  const pos =
    sheetSource && sheetIndex !== null
      ? sheetSource.variants.findIndex((v) => v.index === sheetIndex)
      : -1;

  function handleOpenVariant(sourceId: string, index: number) {
    router.push(`/gallery?v=${sourceId}:${index}`, { scroll: false });
  }

  function handleSheetClose() {
    router.push("/gallery", { scroll: false });
  }

  function handleSheetNav(delta: number) {
    if (!sheetSource || pos < 0) return;
    const next = Math.min(
      Math.max(0, pos + delta),
      sheetSource.variants.length - 1,
    );
    router.push(`/gallery?v=${sheetSource.source_id}:${sheetSource.variants[next].index}`, { scroll: false });
  }

  const filtered = filterSources(allSources, filterMode);
  const sorted = sortSources(filtered, sort);

  const totalVariants = allSources.reduce((acc, s) => acc + s.delivered, 0);

  return (
    <>
      <GalleryToolbar
        count={allSources.length}
        variantCount={totalVariants}
        filterMode={filterMode}
        onFilter={setFilterMode}
        sort={sort}
        onSort={setSort}
      />

      {/* Gallery grid — always mounted; dimmed by the sheet overlay when open */}
      <div style={{ padding: "8px 20px 22px" }}>
        {isLoading && (
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
            Loading gallery…
          </div>
        )}

        {!isLoading && sorted.length === 0 && (
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
            <div style={{ fontSize: 36, opacity: 0.4 }}>⬡</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--color-text)", opacity: 0.6 }}>
              {filterMode === "shortfall" ? "No sources with shortfall" : "No completed runs yet"}
            </div>
            <div style={{ fontSize: 12.5, maxWidth: 320, lineHeight: 1.6 }}>
              {filterMode === "shortfall"
                ? "All sources have delivered their full requested count."
                : "Start a run in the Studio — results appear here after each source completes."}
            </div>
          </div>
        )}

        {sorted.map((source) => (
          <SourceGroup
            key={source.source_id}
            source={source}
            onOpenVariant={handleOpenVariant}
            onRegenerate={() => mutate()}
          />
        ))}
      </div>

      {/* Variant side-panel — mounts over the still-visible grid */}
      {sheetSource && pos >= 0 && (
        <VariantSheet
          sourceId={sheetSource.source_id}
          sourceName={sheetSource.filename.replace(/\.[^.]+$/, "")}
          variants={sheetSource.variants}
          index={pos}
          onClose={handleSheetClose}
          onNav={handleSheetNav}
          onRegenerate={() => mutate()}
        />
      )}
    </>
  );
}

export default function GalleryPage() {
  return (
    <main style={{ minHeight: "100vh" }}>
      <Suspense
        fallback={
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
            Loading…
          </div>
        }
      >
        <GalleryContent />
      </Suspense>
    </main>
  );
}
