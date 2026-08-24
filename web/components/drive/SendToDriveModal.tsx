"use client";
import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { createDriveExport, createDriveExportSplit, splitResultToJobs, listCaptionBanks, previewCaptions } from "@/lib/api";
import {
  CUSTOM_CAPTION_SOURCE,
  captionCustomSourceLabel,
  captionFilenamePreview,
  captionFolderSelectLabel,
  isCustomCaptionSource,
} from "@/lib/captions";
import {
  SPLIT_ROLES,
  assignedTotal,
  autoCountsForSlots,
  formatSlice,
  guessSlotDestinations,
  sliceRanges,
} from "@/lib/packSplit";
import type { CaptionBankFolder, Destination, ExportJob, ExportVariantRef } from "@/lib/types";
import { ExportProgress } from "./ExportProgress";

interface SendToDriveModalProps {
  refs: ExportVariantRef[];
  destinations: Destination[];
  jobId?: string;
  onClose: () => void;
}

const selectStyle = {
  background: "var(--color-panel2)",
  border: "1px solid var(--color-line)",
  borderRadius: 9,
  padding: "9px 12px",
  fontSize: 13,
  color: "var(--color-text)",
  outline: "none",
} as const;

const countStyle = {
  ...selectStyle,
  width: 72,
  padding: "9px 8px",
} as const;

export function SendToDriveModal({ refs, destinations, jobId, onClose }: SendToDriveModalProps) {
  const [destinationId, setDestinationId] = useState(destinations[0]?.id ?? "");
  const [splitMode, setSplitMode] = useState(false);
  const [slotDest, setSlotDest] = useState<string[]>(() => guessSlotDestinations(destinations));
  const [slotCount, setSlotCount] = useState<number[]>(() =>
    autoCountsForSlots(refs.length, guessSlotDestinations(destinations)),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<ExportJob[] | null>(null);
  const [jobRoles, setJobRoles] = useState<Record<string, string>>({});
  const [captions, setCaptions] = useState<string[]>(() => refs.map(() => ""));
  const [fromBank, setFromBank] = useState(false);
  const [banks, setBanks] = useState<CaptionBankFolder[]>([]);
  const [bankId, setBankId] = useState(CUSTOM_CAPTION_SOURCE);
  const custom = isCustomCaptionSource(bankId);

  const ranges = sliceRanges(slotCount);
  const filledDests = slotDest.filter((id) => id.trim().length > 0);
  const assigned = assignedTotal(slotCount.map((n, i) => (slotDest[i] ? n : 0)));
  const uniqueFilled = new Set(filledDests).size === filledDests.length;
  const countsMatch = assigned === refs.length;
  const splitReady = filledDests.length >= 1 && uniqueFilled && countsMatch;
  const canConfirm = splitMode ? splitReady : Boolean(destinationId);

  useEffect(() => {
    let cancelled = false;
    listCaptionBanks()
      .then((list) => {
        if (cancelled) return;
        setBanks(list);
      })
      .catch(() => {/* Custom still works with no folders */});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (isCustomCaptionSource(bankId)) {
      setCaptions(refs.map(() => ""));
      setFromBank(false);
      return;
    }
    let cancelled = false;
    previewCaptions(refs.length, bankId)
      .then((out) => {
        if (cancelled) return;
        if (out.captions.length > 0) {
          setCaptions(out.captions);
          setFromBank(true);
        } else {
          setCaptions(refs.map(() => ""));
          setFromBank(false);
        }
      })
      .catch(() => {/* keep blank captions; VA can type them */});
    return () => { cancelled = true; };
  }, [refs.length, bankId]);

  const captionedRefs = useMemo(
    () => refs.map((ref, i) => ({
      ...ref,
      caption: (captions[i] ?? "").trim() || undefined,
    })),
    [refs, captions],
  );

  async function handleConfirm() {
    if (!canConfirm || submitting) return;
    setSubmitting(true);
    setError(null);
    const useFolder = !custom && fromBank;
    try {
      if (splitMode) {
        const destinationsPayload = SPLIT_ROLES.flatMap((role, i) => {
          const destination_id = slotDest[i];
          const count = slotCount[i] ?? 0;
          if (!destination_id?.trim() || count <= 0) return [];
          return [{ destination_id, label: role.key, count }];
        });
        const created = await createDriveExportSplit({
          job_id: jobId,
          selected: captionedRefs,
          destinations: destinationsPayload,
          consume_bank: useFolder,
          caption_bank_id: useFolder ? bankId : undefined,
        });
        const roles: Record<string, string> = {};
        SPLIT_ROLES.forEach((role, i) => {
          const id = slotDest[i];
          if (id) roles[id] = role.label;
        });
        setJobRoles(roles);
        setJobs(splitResultToJobs(created));
      } else {
        const created = await createDriveExport(
          destinationId,
          captionedRefs,
          useFolder,
          useFolder ? bankId : undefined,
        );
        setJobRoles({ [created.destination_id]: "Destination" });
        setJobs([created]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start export");
    } finally {
      setSubmitting(false);
    }
  }

  function destLabel(job: ExportJob): string {
    const role = jobRoles[job.destination_id];
    const dest = destinations.find((d) => d.id === job.destination_id);
    if (role && dest?.name) return `${role} · ${dest.name}`;
    return role || dest?.name || job.destination_id;
  }

  return (
    <Dialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(23, 42, 46, 0.32)",
            backdropFilter: "blur(3px)",
            zIndex: 60,
          }}
        />
        <Dialog.Content
          aria-describedby={undefined}
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 480,
            maxWidth: "calc(100vw - 32px)",
            maxHeight: "calc(100vh - 48px)",
            overflow: "auto",
            background: "#fbfdfd",
            border: "1px solid #c7dde0",
            borderRadius: 16,
            boxShadow: "0 26px 60px rgba(22, 58, 65, 0.22)",
            zIndex: 61,
            outline: "none",
            padding: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", marginBottom: 16 }}>
            <Dialog.Title style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)", margin: 0 }}>
              Send to Drive
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              style={{
                marginLeft: "auto",
                width: 28,
                height: 28,
                borderRadius: 8,
                background: "transparent",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--color-muted)",
                fontSize: 16,
                cursor: "pointer",
              }}
            >
              ✕
            </Dialog.Close>
          </div>

          {!jobs && (
            <>
              <div style={{ fontSize: 12.5, color: "var(--color-muted)", marginBottom: 14 }}>
                {refs.length} variant{refs.length !== 1 ? "s" : ""} selected. Filename is the
                Repurpose caption — pick a folder or write it yourself.
              </div>

              <label
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  fontSize: 12.5,
                  color: "var(--color-text)",
                  marginBottom: 14,
                }}
              >
                <input
                  type="checkbox"
                  aria-label="Split pack across accounts"
                  checked={splitMode}
                  onChange={(e) => setSplitMode(e.target.checked)}
                  style={{ accentColor: "#7c5cff", marginTop: 2 }}
                />
                <span>
                  Split across accounts
                  <span style={{ display: "block", fontSize: 11, color: "var(--color-muted2)", marginTop: 2 }}>
                    Each account gets different files. Do not send the same file twice.
                  </span>
                </span>
              </label>

              {!splitMode && (
                <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <span style={{ fontSize: 12, color: "var(--color-muted)" }}>Destination</span>
                  <select
                    value={destinationId}
                    onChange={(e) => setDestinationId(e.target.value)}
                    style={selectStyle}
                  >
                    {destinations.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {splitMode && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {SPLIT_ROLES.map((role, i) => {
                    const range = ranges[i];
                    const filled = Boolean(slotDest[i]);
                    return (
                      <div key={role.key} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          <label style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1, minWidth: 0 }}>
                            <span style={{ fontSize: 12, color: "var(--color-muted)" }}>{role.label}</span>
                            <select
                              aria-label={role.label}
                              value={slotDest[i] ?? ""}
                              onChange={(e) => {
                                const next = slotDest.slice();
                                next[i] = e.target.value;
                                setSlotDest(next);
                                setSlotCount(autoCountsForSlots(refs.length, next));
                              }}
                              style={selectStyle}
                            >
                              <option value="">— not used —</option>
                              {destinations.map((d) => (
                                <option key={d.id} value={d.id}>
                                  {d.name}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                            <span style={{ fontSize: 12, color: "var(--color-muted)" }}>Files</span>
                            <input
                              aria-label={`${role.label} count`}
                              type="number"
                              min={0}
                              value={slotCount[i] ?? 0}
                              disabled={!filled}
                              onChange={(e) => {
                                const next = slotCount.slice();
                                const parsed = Number.parseInt(e.target.value, 10);
                                next[i] = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
                                setSlotCount(next);
                              }}
                              style={countStyle}
                            />
                          </label>
                        </div>
                        <span style={{ fontSize: 11, color: "var(--color-muted2)" }}>
                          {filled && range
                            ? formatSlice(range.start, range.end, range.count)
                            : "Leave empty to skip this account"}
                        </span>
                      </div>
                    );
                  })}
                  <div style={{ fontSize: 12, color: countsMatch ? "var(--color-muted)" : "var(--color-red)" }}>
                    {assigned} of {refs.length} assigned
                    {!uniqueFilled && filledDests.length > 1 ? " · pick different folders" : ""}
                  </div>
                </div>
              )}

              <label style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 12 }}>
                <span style={{ fontSize: 12, color: "var(--color-muted)" }}>Caption</span>
                <select
                  value={bankId}
                  onChange={(e) => setBankId(e.target.value)}
                  style={selectStyle}
                >
                  <option value={CUSTOM_CAPTION_SOURCE}>{captionCustomSourceLabel()}</option>
                  {banks.map((b) => (
                    <option key={b.id} value={b.id}>
                      {captionFolderSelectLabel(b.name, b.count, b.remaining)}
                    </option>
                  ))}
                </select>
                <span style={{ fontSize: 11, color: "var(--color-muted2)" }}>
                  {custom
                    ? "Type each Drive filename below. Empty stays v01.mp4. Folder counts are not used."
                    : splitMode
                      ? "One folder names every slice. Filled from that folder — you can still edit a line before send."
                      : "Filled from that folder. You can still edit a line before send."}
                </span>
              </label>

              <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 10, maxHeight: 280, overflow: "auto" }}>
                {refs.map((ref, i) => (
                  <label key={`${ref.source_id}:${ref.index}`} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <span style={{ fontSize: 11.5, color: "var(--color-muted)" }}>
                      v{String(ref.index).padStart(2, "0")} → {captionFilenamePreview(captions[i] ?? "", `v${String(ref.index).padStart(2, "0")}.mp4`)}
                    </span>
                    <textarea
                      value={captions[i] ?? ""}
                      onChange={(e) => {
                        const next = [...captions];
                        next[i] = e.target.value;
                        setCaptions(next);
                      }}
                      rows={2}
                      placeholder={custom ? "Write the caption (Drive filename)" : "Caption (Drive filename)"}
                      style={{
                        background: "var(--color-panel2)",
                        border: "1px solid var(--color-line)",
                        borderRadius: 9,
                        padding: "8px 10px",
                        fontSize: 12.5,
                        color: "var(--color-text)",
                        outline: "none",
                        resize: "vertical",
                      }}
                    />
                  </label>
                ))}
              </div>

              {error && (
                <div style={{ fontSize: 12, color: "var(--color-red)", marginTop: 10 }}>{error}</div>
              )}

              <div style={{ display: "flex", gap: 8, marginTop: 18, justifyContent: "flex-end" }}>
                <button
                  onClick={onClose}
                  style={{
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: "var(--color-text)",
                    background: "var(--color-panel2)",
                    border: "1px solid var(--color-line)",
                    padding: "8px 14px",
                    borderRadius: 9,
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={submitting || !canConfirm}
                  style={{
                    fontSize: 12.5,
                    fontWeight: 700,
                    color: "#fff",
                    background: "#172124",
                    border: "none",
                    padding: "8px 16px",
                    borderRadius: 9,
                    cursor: submitting || !canConfirm ? "not-allowed" : "pointer",
                    opacity: submitting || !canConfirm ? 0.7 : 1,
                  }}
                >
                  {submitting ? "Starting…" : splitMode ? "Split send" : "Confirm"}
                </button>
              </div>
            </>
          )}

          {jobs && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {jobs.map((job) => (
                <div key={job.export_id}>
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: "var(--color-text)",
                      marginBottom: 8,
                    }}
                  >
                    {destLabel(job)}
                  </div>
                  <ExportProgress exportId={job.export_id} initial={job} />
                </div>
              ))}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
