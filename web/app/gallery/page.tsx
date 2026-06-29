"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useGallery } from "@/lib/useGallery";
import { useRun } from "@/lib/runStore";
import { filterSources, sortSources } from "@/lib/gallery";
import { GalleryToolbar } from "@/components/gallery/GalleryToolbar";
import { SourceGroup } from "@/components/gallery/SourceGroup";

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

  // Read ?v= param (side-panel will be Task 9 — no-op handler here)
  const vParam = searchParams.get("v");
  // TODO(Task 9): open variant side-panel when vParam is set
  void vParam;

  function handleOpenVariant(sourceId: string, index: number) {
    // Set URL param — the actual sheet is Task 9
    router.push(`/gallery?v=${sourceId}:${index}`, { scroll: false });
  }

  const allSources = sources ?? [];
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
