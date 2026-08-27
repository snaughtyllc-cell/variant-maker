"use client";
import { Suspense, useEffect, useRef, useState } from "react";
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
  fillFileCache,
  filesReadyNow,
  phoneShareHintCopy,
  preparingClipsCopy,
  saveNoneSelectedCopy,
  saveOrShareVideoFiles,
  selectedShareableVariants,
  shareEmptyCopy,
  shareLoadingCopy,
  shareOutcomeMessage,
  shareRetryCopy,
  shareVideosBusyLabel,
  shareVideosLabel,
  shouldOfferPhotosSave,
} from "@/lib/shareVideos";
import { getDriveStatus, listDestinations } from "@/lib/api";
import type { Destination, DriveStatus, SourceOut } from "@/lib/types";
import { GalleryToolbar } from "@/components/gallery/GalleryToolbar";
import { GalleryFloatingToolbar } from "@/components/gallery/GalleryFloatingToolbar";
import { PackList } from "@/components/gallery/PackList";
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
  const [selectedPackId, setSelectedPackId] = useState<string | null>(null);
  const [packSearch, setPackSearch] = useState("");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [driveStatus, setDriveStatus] = useState<DriveStatus | null>(null);
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [sendModalOpen, setSendModalOpen] = useState(false);
  const [sheetQuery, setSheetQuery] = useState<{ sourceId: string; index: number } | null | undefined>(
    undefined,
  );
  const [offerPhotos, setOfferPhotos] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [pendingShareFiles, setPendingShareFiles] = useState<File[] | null>(null);
  const [clipsPrepared, setClipsPrepared] = useState(false);
  const fileCacheRef = useRef(new Map<string, File>());

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
    const nav = typeof navigator === "undefined" ? undefined : navigator;
    setOfferPhotos(shouldOfferPhotosSave(nav, nav?.userAgent, nav?.maxTouchPoints));
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
    setSelectedPackId(sourceId);
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

  // A deep-linked/open variant sheet (via ?v=) takes priority so the PACKS
  // list stays focused on it; otherwise the last pack clicked, else the top one.
  const activePackId = activeQuery?.sourceId ?? selectedPackId ?? undefined;
  const activePack = sorted.find((s) => s.source_id === activePackId) ?? sorted[0];

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
  const selectedKey = [...selected].sort().join(",");
  const selectedVariants = selectedShareableVariants(allSources, selected);

  useEffect(() => {
    if (selectedVariants.length === 0) {
      setClipsPrepared(false);
      setPendingShareFiles(null);
      setSaveMsg(null);
      return;
    }
    let cancelled = false;
    setClipsPrepared(false);
    void fillFileCache(fileCacheRef.current, selectedVariants).then((files) => {
      if (cancelled) return;
      setClipsPrepared(files.length === selectedVariants.length);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedKey, sources]);

  function handleSelectAllVisible() {
    setSelected((prev) => withOkSelection(prev, sorted, !allVisibleSelected));
  }

  function handleToggleSelectSource(source: SourceOut, select: boolean) {
    setSelected((prev) => withOkSelection(prev, [source], select));
  }

  function handleSaveSelected() {
    if (saveBusy || okRefs.length === 0) return;
    const nav = typeof navigator === "undefined" ? undefined : navigator;
    const ready = filesReadyNow(fileCacheRef.current, selectedVariants, pendingShareFiles);
    if (!ready) {
      setSaveBusy(true);
      setSaveMsg(shareLoadingCopy());
      void fillFileCache(fileCacheRef.current, selectedVariants)
        .then((files) => {
          setClipsPrepared(files.length === selectedVariants.length);
          setPendingShareFiles(files.length ? files : null);
          setSaveMsg(files.length ? shareRetryCopy() : shareEmptyCopy());
        })
        .catch(() => setSaveMsg(shareEmptyCopy()))
        .finally(() => setSaveBusy(false));
      return;
    }
    setSaveBusy(true);
    setSaveMsg(null);
    void saveOrShareVideoFiles(ready, {
      share: nav,
      userAgent: nav?.userAgent,
      maxTouchPoints: nav?.maxTouchPoints,
    })
      .then((outcome) => {
        if (outcome.result === "needs_gesture") {
          setPendingShareFiles(outcome.remaining);
          setSaveMsg(shareOutcomeMessage(outcome));
          return;
        }
        setPendingShareFiles(null);
        if (outcome.result === "unsupported") setSaveMsg(shareEmptyCopy());
      })
      .catch(() => setSaveMsg(shareEmptyCopy()))
      .finally(() => setSaveBusy(false));
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
    <main className="gallery-page">
      <GalleryToolbar
        count={sorted.length}
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
        saveLabel={saveBusy ? shareVideosBusyLabel() : shareVideosLabel(offerPhotos)}
        saveBusy={saveBusy}
        saveDisabledReason={
          okRefs.length === 0
            ? saveNoneSelectedCopy()
            : offerPhotos && !clipsPrepared && !pendingShareFiles
              ? preparingClipsCopy()
              : null
        }
        saveHint={phoneShareHintCopy()}
        onSave={() => { handleSaveSelected(); }}
        saveMsg={saveMsg}
      />

      <div className="gallery-body">
        <PackList
          packs={sorted}
          totalCount={sorted.length}
          activeId={activePack?.source_id}
          onSelect={setSelectedPackId}
          search={packSearch}
          onSearchChange={setPackSearch}
          loading={isLoading}
        />

        {/* Grid pane — always mounted; dimmed by the sheet overlay when open */}
        <section className="gallery-grid-pane">
          {isLoading && <div className="gallery-loading">Loading gallery…</div>}

          {!isLoading && sorted.length === 0 && (
            <div className="gallery-empty">
              <div className="gallery-empty__icon">⬡</div>
              <strong>{filterMode === "shortfall" ? "No packs need attention" : "No completed runs yet"}</strong>
              <p>
                {filterMode === "shortfall"
                  ? "All packs have delivered their full requested count."
                  : "Start a run in Studio and stay on that page until variant tiles appear. Gallery only lists finished variants — and a Studio redeploy clears unfinished jobs."}
              </p>
            </div>
          )}

          {!isLoading && activePack && (
            <SourceGroup
              key={activePack.source_id}
              source={activePack}
              onOpenVariant={handleOpenVariant}
              onRegenerate={() => mutate()}
              selected={selected}
              onToggleVariant={handleToggleVariant}
              onToggleSelectSource={handleToggleSelectSource}
              onRemove={() => handleRemoveSource(activePack)}
            />
          )}

          {selected.size > 0 && (
            <GalleryFloatingToolbar
              count={selected.size}
              onSend={() => setSendModalOpen(true)}
              sendDisabled={disabledReason != null}
              sendTitle={disabledReason}
              onSave={handleSaveSelected}
              saveLabel={saveBusy ? shareVideosBusyLabel() : shareVideosLabel(offerPhotos)}
              saveDisabled={
                saveBusy ||
                okRefs.length === 0 ||
                (offerPhotos && !clipsPrepared && !pendingShareFiles)
              }
              saveTitle={phoneShareHintCopy()}
              onClose={() => setSelected(new Set())}
            />
          )}
        </section>
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
