"use client";
import { Suspense, useEffect, useState } from "react";
import { FolderOpen } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useGallery } from "@/lib/useGallery";
import { useRun } from "@/lib/runStore";
import {
  filterSources,
  sortSources,
  filesReadyCount,
  parseGalleryVariantQuery,
  gallerySearchPath,
  pushGallerySearch,
} from "@/lib/gallery";
import {
  okVariantKeys,
  okVariantRefs,
  selectAllLabel,
  selectionHasAllOk,
  sendDisabledReason,
  withOkSelection,
} from "@/lib/drive";
import {
  canShareVideoFiles,
  fetchVariantFiles,
  phoneShareHintCopy,
  saveNoneSelectedCopy,
  saveOrShareVideoFiles,
  selectedShareableVariants,
  shareEmptyCopy,
  shareVideosBusyLabel,
  shareVideosLabel,
} from "@/lib/shareVideos";
import { getDriveStatus, listDestinations } from "@/lib/api";
import type { Destination, DriveStatus, SourceOut } from "@/lib/types";
import { GalleryToolbar } from "@/components/gallery/GalleryToolbar";
import { SourceGroup } from "@/components/gallery/SourceGroup";
import { VariantSheet } from "@/components/variant/VariantSheet";
import { SendToDriveModal } from "@/components/drive/SendToDriveModal";

type FilterMode = "all" | "shortfall";
type SortMode = "newest";

export function GalleryContent() {
  const { data: sources, mutate, isLoading } = useGallery();
  const { complete } = useRun();
  const searchParams = useSearchParams();

  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [sort, setSort] = useState<SortMode>("newest");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [driveStatus, setDriveStatus] = useState<DriveStatus | null>(null);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [sendModalOpen, setSendModalOpen] = useState(false);
  const [sheetQuery, setSheetQuery] = useState<{ sourceId: string; index: number } | null | undefined>(
    undefined,
  );
  const [canShare, setCanShare] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  // Load Drive status + destinations once, in parallel with the gallery SWR fetch.
  useEffect(() => {
    Promise.all([getDriveStatus(), listDestinations()])
      .then(([status, dests]) => {
        setDriveStatus(status);
        setDestinations(dests);
      })
      .catch((e) => console.error("Failed to load Drive status", e));
  }, []);

  useEffect(() => {
    setCanShare(canShareVideoFiles(typeof navigator === "undefined" ? undefined : navigator));
  }, []);

  function handleToggleVariant(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // Revalidate gallery when active run completes
  useEffect(() => {
    if (complete) {
      mutate();
    }
  }, [complete, mutate]);

  // `undefined` = follow the address bar (deep link). Local value opens/closes
  // immediately so we never wait on a Next.js remount.
  const urlQuery = parseGalleryVariantQuery(searchParams.get("v"));
  const activeQuery = sheetQuery === undefined ? urlQuery : sheetQuery;

  const allSources = sources ?? [];
  const sheetSource = activeQuery
    ? allSources.find((s) => s.source_id === activeQuery.sourceId)
    : undefined;
  const sheetIndex = activeQuery?.index ?? null;
  const pos =
    sheetSource && sheetIndex !== null
      ? sheetSource.variants.findIndex((v) => v.index === sheetIndex)
      : -1;

  function handleOpenVariant(sourceId: string, index: number) {
    setSheetQuery({ sourceId, index });
    pushGallerySearch(gallerySearchPath(sourceId, index));
  }

  function handleSheetClose() {
    setSheetQuery(null);
    pushGallerySearch(gallerySearchPath());
  }

  function handleSheetNav(delta: number) {
    if (!sheetSource || pos < 0) return;
    const next = Math.min(
      Math.max(0, pos + delta),
      sheetSource.variants.length - 1,
    );
    const index = sheetSource.variants[next].index;
    setSheetQuery({ sourceId: sheetSource.source_id, index });
    pushGallerySearch(gallerySearchPath(sheetSource.source_id, index));
  }

  useEffect(() => {
    function onPop() {
      setSheetQuery(parseGalleryVariantQuery(new URLSearchParams(window.location.search).get("v")));
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const filtered = filterSources(allSources, filterMode);
  const sorted = sortSources(filtered, sort);

  const totalVariants = allSources.reduce((acc, s) => acc + filesReadyCount(s), 0);

  const okRefs = okVariantRefs(allSources, selected);
  const selectedJobIds = [
    ...new Set(
      okRefs
        .map((r) => allSources.find((s) => s.source_id === r.source_id)?.job_id)
        .filter((id): id is string => Boolean(id)),
    ),
  ];
  const splitJobId = selectedJobIds.length === 1 ? selectedJobIds[0] : undefined;
  const disabledReason = sendDisabledReason(driveStatus, destinations, okRefs);
  const visibleOkCount = okVariantKeys(sorted).length;
  const allVisibleSelected = selectionHasAllOk(selected, sorted);

  function handleSelectAllVisible() {
    setSelected((prev) => withOkSelection(prev, sorted, !allVisibleSelected));
  }

  function handleToggleSelectSource(source: SourceOut, select: boolean) {
    setSelected((prev) => withOkSelection(prev, [source], select));
  }

  async function handleSaveSelected() {
    if (saveBusy || okRefs.length === 0) return;
    setSaveBusy(true);
    setSaveMsg(null);
    try {
      const files = await fetchVariantFiles(selectedShareableVariants(allSources, selected));
      if (files.length === 0) {
        setSaveMsg(shareEmptyCopy());
        return;
      }
      const nav = typeof navigator === "undefined" ? undefined : navigator;
      await saveOrShareVideoFiles(files, { share: nav });
    } catch {
      setSaveMsg(shareEmptyCopy());
    } finally {
      setSaveBusy(false);
    }
  }

  function handleRemoveSource(source: SourceOut) {
    setSelected((prev) => {
      const next = new Set(prev);
      const prefix = `${source.source_id}:`;
      for (const key of [...next]) {
        if (key.startsWith(prefix)) next.delete(key);
      }
      return next;
    });
    mutate();
  }

  function handleSendModalClose() {
    setSendModalOpen(false);
    setSelected(new Set());
  }

  return (
    <main className="workspace-page gallery-page">
      <section className="workspace-page-shell">
        <header className="workspace-heading">
          <span className="workspace-heading__icon"><FolderOpen size={19} /></span>
          <div>
            <p className="workspace-heading__eyebrow">Review library</p>
            <h1>Gallery</h1>
            <p className="workspace-heading__copy">Finished packs by source. Select clips, then Save to Photos on a phone — or send copies to Drive.</p>
          </div>
        </header>
      </section>
      <GalleryToolbar
        count={allSources.length}
        variantCount={totalVariants}
        filterMode={filterMode}
        onFilter={setFilterMode}
        sort={sort}
        onSort={setSort}
        selectedCount={okRefs.length}
        sendDisabledReason={disabledReason}
        onSend={() => setSendModalOpen(true)}
        selectAllLabel={selectAllLabel(allVisibleSelected)}
        selectAllDisabled={visibleOkCount === 0}
        onSelectAll={handleSelectAllVisible}
        saveLabel={saveBusy ? shareVideosBusyLabel() : shareVideosLabel(canShare)}
        saveBusy={saveBusy}
        saveDisabledReason={okRefs.length === 0 ? saveNoneSelectedCopy() : null}
        saveHint={phoneShareHintCopy()}
        onSave={() => { void handleSaveSelected(); }}
        saveMsg={saveMsg}
      />

      {/* Gallery grid — always mounted; dimmed by the sheet overlay when open */}
      <div className="gallery-content" style={{ padding: "8px 16px 22px" }}>
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
                : "Start a run in Studio and stay on that page until variant tiles appear. Gallery only lists finished variants — and a Studio redeploy clears unfinished jobs."}
            </div>
          </div>
        )}

        {sorted.map((source) => (
          <SourceGroup
            key={source.source_id}
            source={source}
            onOpenVariant={handleOpenVariant}
            onRegenerate={() => mutate()}
            selected={selected}
            onToggleVariant={handleToggleVariant}
            onToggleSelectSource={handleToggleSelectSource}
            onRemove={() => handleRemoveSource(source)}
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

      {/* Send to Drive modal — only opened when the toolbar button is enabled */}
      {sendModalOpen && (
        <SendToDriveModal
          refs={okRefs}
          destinations={destinations}
          jobId={splitJobId}
          onClose={handleSendModalClose}
        />
      )}
    </main>
  );
}

export default function GalleryPage() {
  return (
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
  );
}
