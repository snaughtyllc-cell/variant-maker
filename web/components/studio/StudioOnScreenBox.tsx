"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState, useRef } from "react";
import {
  deleteOnScreenTemplate,
  listOnScreenTemplates,
  saveOnScreenTemplate,
  soundFileKind,
  soundSizeNote,
  type OnScreenTemplate,
} from "@/lib/api";
import { captureVideoFrame } from "@/lib/videoPoster";

export type OnScreenStyle = "classic" | "strong" | "caption-bar";
export type OnScreenBackground = "solid" | "see-through" | "none" | "plain";

export type OnScreenAudio = {
  id: string;
  name: string;
  volume: number;
  mode: "under" | "replace";
  start: number;
  key?: string;
  bed_id?: string;
  file?: File;
};

export type OnScreenCaption = {
  id: string;
  text: string;
  box_ids: string[];
  place?: Record<string, { x: number; y: number }>;
  size?: number;
  lines?: 1 | 2 | "both";
};

export const MAX_SOUNDS = 4;
export const MAX_PRINTS = 5;
export const MAX_PACK = 40;

export function cleanAudios(audios: OnScreenAudio[] | undefined, previewId?: string): OnScreenAudio[] {
  const rows = (audios || []).slice(0, MAX_SOUNDS).flatMap((audio) => {
    const row: OnScreenAudio = {
      id: audio.id,
      name: (audio.name || "Sound").slice(0, 80),
      volume: Math.min(1, Math.max(0, Number(audio.volume ?? 0.25) || 0)),
      mode: audio.mode === "replace" ? "replace" : "under",
      start: Math.min(30, Math.max(0, Number(audio.start) || 0)),
      ...(audio.key ? { key: audio.key } : {}),
      ...(audio.bed_id ? { bed_id: audio.bed_id } : {}),
      ...(audio.file ? { file: audio.file } : {}),
    };
    return row.key || row.bed_id || row.file ? [row] : [];
  });
  const index = previewId ? rows.findIndex((audio) => audio.id === previewId) : 0;
  if (index <= 0) return rows;
  return [...rows.slice(index), ...rows.slice(0, index)];
}

export function printPlan(perVideo: number, prints: number): { each: number; total: number } {
  const n = Math.max(1, Math.min(MAX_PRINTS, Math.floor(prints) || 1));
  const want = Math.max(1, Math.floor(perVideo) || 1);
  const each = Math.max(1, Math.min(want, Math.floor(MAX_PACK / n)));
  return { each, total: each * n };
}

export function projectWithPrints(prints: OnScreenProject[]): OnScreenProject {
  const first = prints[0];
  return { ...first, prints: prints.slice(0, MAX_PRINTS) };
}

export function seatStyle(x: number, y: number): {
  left?: string;
  right?: string;
  top?: string;
  bottom?: string;
  transform: string;
  transformOrigin: string;
} {
  const col = x <= 0.34 ? "start" : x >= 0.66 ? "end" : "center";
  const row = y <= 0.34 ? "start" : y >= 0.66 ? "end" : "center";
  const style: {
    left?: string;
    right?: string;
    top?: string;
    bottom?: string;
    transform: string;
    transformOrigin: string;
  } = {
    transform: `translate(${col === "center" ? "-50%" : "0"}, ${row === "center" ? "-50%" : "0"})`,
    transformOrigin: `${col === "end" ? "right" : col === "start" ? "left" : "center"} ${row === "end" ? "bottom" : row === "start" ? "top" : "center"}`,
  };
  if (col === "end") {
    style.right = "4%";
    style.left = "auto";
  } else if (col === "center") style.left = "50%";
  else style.left = "4%";
  if (row === "end") {
    style.bottom = "4%";
    style.top = "auto";
  } else if (row === "center") style.top = "50%";
  else style.top = "4%";
  return style;
}

export function textFitWarning(textWidth: number, boxWidth: number): string {
  if (boxWidth <= 0 || textWidth <= boxWidth * 0.92) return "";
  return "This line is too big for that seat. Make it smaller so it stays inside the box.";
}

export function clampTextSize(value: number) {
  const stepped = Math.round(value * 10) / 10;
  return Math.min(1.6, Math.max(0.55, stepped));
}

export const TEXT_SEATS = [
  { id: "tl", label: "Top left", x: 0.18, y: 0.18 },
  { id: "tc", label: "Top", x: 0.5, y: 0.18 },
  { id: "tr", label: "Top right", x: 0.82, y: 0.18 },
  { id: "ml", label: "Left", x: 0.18, y: 0.5 },
  { id: "mc", label: "Center", x: 0.5, y: 0.5 },
  { id: "mr", label: "Right", x: 0.82, y: 0.5 },
  { id: "bl", label: "Bottom left", x: 0.18, y: 0.82 },
  { id: "bc", label: "Bottom", x: 0.5, y: 0.82 },
  { id: "br", label: "Bottom right", x: 0.82, y: 0.82 },
] as const;

export type OnScreenBox = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  seats?: string[];
};

export type OnScreenProject = {
  captions: OnScreenCaption[];
  boxes: OnScreenBox[];
  chooseSeats?: boolean;
  look: { style: OnScreenStyle; background: OnScreenBackground; color: string };
  audios?: OnScreenAudio[];
  previewAudio?: string;
  prints?: OnScreenProject[];
};

export const BOX_COLORS = [
  { id: "cyan", label: "Cyan", hex: "#14b8c4" },
  { id: "amber", label: "Amber", hex: "#e39b12" },
  { id: "pink", label: "Pink", hex: "#e85d8c" },
  { id: "violet", label: "Violet", hex: "#7c5cff" },
] as const;

export const FRAME_PRESETS = [
  { id: "9:16", w: 9, h: 16 },
  { id: "3:4", w: 3, h: 4 },
  { id: "4:5", w: 4, h: 5 },
  { id: "1:1", w: 1, h: 1 },
  { id: "4:3", w: 4, h: 3 },
  { id: "16:9", w: 16, h: 9 },
] as const;

export function frameAspect(
  preset: string | null,
  width?: number,
  height?: number,
): { css: string; w: number; h: number } {
  const picked = FRAME_PRESETS.find((item) => item.id === preset);
  if (picked) return { css: `${picked.w} / ${picked.h}`, w: picked.w, h: picked.h };
  if (width && height && width > 0 && height > 0) {
    return { css: `${Math.round(width)} / ${Math.round(height)}`, w: width, h: height };
  }
  return { css: "9 / 16", w: 9, h: 16 };
}

const MIN_BOX = 0.06;
export const REEL_SAFE = { top: 0.08, bottom: 0.08, right: 0.14 };
const HANDLES = ["nw", "ne", "sw", "se"] as const;

type Handle = (typeof HANDLES)[number];

type Drag =
  | { kind: "draw"; pointerId: number; x0: number; y0: number; x1: number; y1: number }
  | { kind: "move"; pointerId: number; id: string; dx: number; dy: number }
  | { kind: "resize"; pointerId: number; id: string; handle: Handle }
  | { kind: "text"; pointerId: number; id: string };

export function emptyOnScreen(): OnScreenProject {
  return {
    captions: [{ id: "1", text: "", box_ids: [] }],
    boxes: [],
    audios: [],
    look: { style: "classic", background: "solid", color: "#FFFFFF" },
  };
}

export function draftFromSaved(project: OnScreenProject): OnScreenProject {
  const boxes = (project.boxes || []).map((box) => ({
    ...box,
    color: BOX_COLORS.find((color) => color.id === box.id)?.hex || box.color || "#14b8c4",
  }));
  const blank = emptyOnScreen();
  return {
    captions: project.captions?.length ? project.captions : blank.captions,
    boxes,
    chooseSeats: boxes.some((box) => (box.seats || []).length > 0),
    look: project.look || blank.look,
    audios: project.audios || [],
    previewAudio: project.audios?.[0]?.id,
  };
}

export function rectFromPoints(x0: number, y0: number, x1: number, y1: number) {
  return {
    x: Math.min(x0, x1),
    y: Math.min(y0, y1),
    w: Math.abs(x1 - x0),
    h: Math.abs(y1 - y0),
  };
}

export function clampBox(box: { x: number; y: number; w: number; h: number }) {
  const w = Math.min(1, Math.max(MIN_BOX, box.w));
  const h = Math.min(1, Math.max(MIN_BOX, box.h));
  return {
    x: Math.min(Math.max(0, box.x), 1 - w),
    y: Math.min(Math.max(0, box.y), 1 - h),
    w,
    h,
  };
}

function pointInFrame(event: { clientX: number; clientY: number }, frame: DOMRect) {
  const x = (event.clientX - frame.left) / frame.width;
  const y = (event.clientY - frame.top) / frame.height;
  return {
    x: Math.min(1, Math.max(0, x)),
    y: Math.min(1, Math.max(0, y)),
  };
}

export function projectFromDraft(draft: OnScreenProject): OnScreenProject | string {
  const boxes = draft.boxes.slice(0, 4).map((box) => {
    const fitted = clampBox(box);
    const seats = draft.chooseSeats
      ? (box.seats || []).filter((id, index, all) => TEXT_SEATS.some((seat) => seat.id === id) && all.indexOf(id) === index)
      : [];
    return { id: box.id, ...fitted, color: box.color, ...(seats.length ? { seats } : {}) };
  });
  const known = new Set(boxes.map((box) => box.id));
  const captions = draft.captions
    .map((cap, i) => {
      const box_ids = cap.box_ids.filter((id) => known.has(id));
      const place: Record<string, { x: number; y: number }> = {};
      for (const id of box_ids) {
        const spot = cap.place?.[id];
        place[id] = {
          x: Math.min(1, Math.max(0, spot?.x ?? 0.5)),
          y: Math.min(1, Math.max(0, spot?.y ?? 0.5)),
        };
      }
      return {
        id: String(i + 1),
        text: cap.text.trim(),
        box_ids,
        place,
        ...(cap.size ? { size: clampTextSize(cap.size) } : {}),
        ...(cap.lines === 1 || cap.lines === 2 || cap.lines === "both" ? { lines: cap.lines } : {}),
      };
    })
    .filter((cap) => cap.text || cap.box_ids.length);
  if (captions.length === 0) return "Add one on-screen line.";
  if (captions.length > 4) return "At most 4 on-screen lines.";
  if (captions.some((cap) => !cap.text)) return "Each on-screen line needs words.";
  if (captions.some((cap) => cap.box_ids.length === 0)) return "Each line needs a box.";
  const used = captions.flatMap((cap) => cap.box_ids);
  if (new Set(used).size !== used.length) return "Each box locks to one line.";
  if (boxes.some((box) => !used.includes(box.id))) return "Lock every colored box to a line.";
  const audios = cleanAudios(draft.audios, draft.previewAudio);
  return {
    captions,
    boxes,
    look: draft.look,
    ...(audios.length ? { audios } : {}),
  };
}

export function captionsWithNewBox(captions: OnScreenCaption[], boxId: string) {
  const open = captions.findIndex((cap) => cap.box_ids.length === 0);
  const index = open >= 0 ? open : captions.length === 1 ? 0 : -1;
  if (index < 0) return captions;
  return captions.map((cap, i) => (
    i === index ? { ...cap, box_ids: [...cap.box_ids, boxId] } : cap
  ));
}

function nextColor(boxes: OnScreenBox[]) {
  const used = new Set(boxes.map((box) => box.id));
  return BOX_COLORS.find((color) => !used.has(color.id)) ?? null;
}

function colorOf(box: OnScreenBox) {
  return BOX_COLORS.find((color) => color.id === box.id)?.hex || box.color;
}

export type OnScreenPreview = {
  key: string;
  name: string;
  file?: File;
  src?: string;
  width?: number;
  height?: number;
};

export function projectsForSources(
  sources: { key: string; name: string }[],
  byKey: Record<string, OnScreenProject>,
): OnScreenProject[] | string {
  const out: OnScreenProject[] = [];
  for (const source of sources) {
    const built = projectFromDraft(byKey[source.key] ?? emptyOnScreen());
    if (typeof built === "string") return `${source.name}: ${built}`;
    out.push(built);
  }
  return out;
}

export function StudioOnScreenBox({
  enabled,
  onEnabledChange,
  draft: sharedDraft,
  onChange: onSharedChange,
  projects,
  onProjectsChange,
  sources = [],
  perVideo = 4,
  onPrintsChange,
}: {
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  draft: OnScreenProject;
  onChange: (next: OnScreenProject) => void;
  projects?: Record<string, OnScreenProject>;
  onProjectsChange?: (next: Record<string, OnScreenProject>) => void;
  sources?: OnScreenPreview[];
  perVideo?: number;
  onPrintsChange?: (prints: OnScreenProject[]) => void;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [open, setOpen] = useState(enabled);
  const [clipIndex, setClipIndex] = useState(0);
  const [poster, setPoster] = useState("");
  const [fitWarning, setFitWarning] = useState("");
  const [templates, setTemplates] = useState<OnScreenTemplate[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [pickedPrints, setPickedPrints] = useState<string[]>([]);
  const [setupNote, setSetupNote] = useState("");
  const [playing, setPlaying] = useState("");
  const [tool, setTool] = useState<"text" | "sound" | "setups">("text");
  const [selectedSound, setSelectedSound] = useState("");
  const soundInputRef = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef("");
  const previewAudioRef = useRef<HTMLMediaElement | null>(null);
  const [sourceSize, setSourceSize] = useState<{ w: number; h: number } | null>(null);
  const [framePreset, setFramePreset] = useState<string | null>(null);
  const clip = sources[Math.min(clipIndex, Math.max(0, sources.length - 1))];
  const draft = projects && clip ? (projects[clip.key] ?? emptyOnScreen()) : sharedDraft;

  function onChange(next: OnScreenProject) {
    if (projects && clip && onProjectsChange) {
      onProjectsChange({ ...projects, [clip.key]: next });
      return;
    }
    onSharedChange(next);
  }
  const aspect = frameAspect(framePreset, sourceSize?.w, sourceSize?.h);

  useEffect(() => {
    if (!clip) {
      setPoster("");
      setSourceSize(null);
      return;
    }
    if (!clip.file) {
      setPoster(clip.src || "");
      setSourceSize(clip.width && clip.height ? { w: clip.width, h: clip.height } : null);
      return;
    }
    let cancel = false;
    captureVideoFrame(clip.file)
      .then((frame) => {
        if (cancel) return;
        setPoster(frame.poster);
        setSourceSize({ w: frame.width, h: frame.height });
      })
      .catch(() => {
        if (!cancel) {
          setPoster(clip.src || "");
          setSourceSize(null);
        }
      });
    return () => {
      cancel = true;
    };
  }, [clip?.key, clip?.file, clip?.src, clip?.width, clip?.height]);

  useEffect(() => {
    if (!(enabled && open)) return;
    let cancel = false;
    listOnScreenTemplates()
      .then((rows) => {
        if (!cancel) setTemplates(rows);
      })
      .catch(() => {
        if (!cancel) setTemplates([]);
      });
    return () => {
      cancel = true;
    };
  }, [enabled, open]);

  function closeEditor(next: boolean) {
    setOpen(next);
    if (next) return;
    previewAudioRef.current?.pause();
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = "";
    }
    setPlaying("");
  }

  useEffect(() => {
    const node = frameRef.current?.querySelector("[data-role='text']") as HTMLElement | null;
    const box = node?.closest(".studio-onscreen__box") as HTMLElement | null;
    if (!node || !box) {
      setFitWarning("");
      return;
    }
    setFitWarning(textFitWarning(node.scrollWidth, box.clientWidth));
  }, [draft, poster]);

  function toggleSeat(seatId: string) {
    const seat = TEXT_SEATS.find((item) => item.id === seatId);
    const box = draft.boxes.find((item) => item.id === selected) || draft.boxes[0];
    if (!seat || !box) return;
    const current = box.seats || [];
    const turningOff = current.includes(seatId);
    const seats = turningOff ? current.filter((id) => id !== seatId) : [...current, seatId];
    const nextSeat = TEXT_SEATS.find((item) => item.id === seats[0]);
    onChange({
      ...draft,
      chooseSeats: true,
      boxes: draft.boxes.map((item) => (item.id === box.id ? { ...item, seats } : item)),
      captions: draft.captions.map((cap) => {
        if (!cap.box_ids.includes(box.id)) return cap;
        const place = { ...(cap.place || {}) };
        if (!turningOff) place[box.id] = { x: seat.x, y: seat.y };
        else if (nextSeat) place[box.id] = { x: nextSeat.x, y: nextSeat.y };
        return { ...cap, place };
      }),
    });
  }

  function toggleLine(which: 1 | 2) {
    const current = draft.captions[0]?.lines;
    const has1 = current === 1 || current === "both";
    const has2 = current === 2 || current === "both";
    const next1 = which === 1 ? !has1 : has1;
    const next2 = which === 2 ? !has2 : has2;
    const lines = next1 && next2 ? "both" as const : next1 ? 1 : next2 ? 2 : undefined;
    setFit({ lines, size: draft.captions[0]?.size ?? 1 });
  }

  function patchAudio(id: string, next: Partial<OnScreenAudio>) {
    onChange({
      ...draft,
      audios: (draft.audios || []).map((audio) => (audio.id === id ? { ...audio, ...next } : audio)),
    });
  }

  function addSounds(list: FileList | null) {
    const incoming = Array.from(list || []).filter((file) => soundFileKind(file));
    if (!incoming.length) return;
    const tooBig = incoming.find((file) => soundSizeNote(file));
    if (tooBig) {
      setSetupNote(soundSizeNote(tooBig) || "That file is too big.");
      return;
    }
    const room = MAX_SOUNDS - (draft.audios || []).length;
    if (room <= 0) {
      setSetupNote("At most 4 sounds.");
      return;
    }
    const added: OnScreenAudio[] = incoming.slice(0, room).map((file, index) => ({
      id: `s${Date.now().toString(36)}${index}`,
      name: file.name.replace(/\.[^.]+$/, "").slice(0, 80) || "Sound",
      volume: 0.25,
      mode: "under",
      start: 0,
      file,
    }));
    setSetupNote("");
    setTool("sound");
    setSelectedSound(added[0].id);
    onChange({
      ...draft,
      audios: [...(draft.audios || []), ...added],
      previewAudio: draft.previewAudio || added[0].id,
    });
  }

  function removeSound(id: string) {
    const audios = (draft.audios || []).filter((audio) => audio.id !== id);
    onChange({
      ...draft,
      audios,
      previewAudio: draft.previewAudio === id ? audios[0]?.id : draft.previewAudio,
    });
    if (playing === id) {
      previewAudioRef.current?.pause();
      setPlaying("");
    }
  }

  function playSound(audio: OnScreenAudio) {
    const el = previewAudioRef.current || document.createElement("video");
    previewAudioRef.current = el;
    setSelectedSound(audio.id);
    if (playing === audio.id) {
      el.pause();
      setPlaying("");
      return;
    }
    let src = "";
    if (audio.file) {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      src = URL.createObjectURL(audio.file);
      previewUrlRef.current = src;
    } else if (audio.bed_id) {
      src = `/api/onscreen/beds/${audio.bed_id}`;
    }
    if (!src) return;
    el.src = src;
    el.onended = () => setPlaying("");
    void el.play().then(() => setPlaying(audio.id)).catch(() => setSetupNote("Could not play that sound."));
    onChange({ ...draft, previewAudio: audio.id });
  }

  function setSoundMode(audio: OnScreenAudio, mode: "under" | "replace") {
    const volume = mode === "replace" && audio.volume <= 0.25
      ? 1
      : mode === "under" && audio.volume === 1
        ? 0.25
        : audio.volume;
    patchAudio(audio.id, { mode, volume });
  }

  function reportPrints(ids: string[], rows: OnScreenTemplate[] = templates) {
    const selected = rows.filter((row) => ids.includes(row.id)).slice(0, MAX_PRINTS);
    onPrintsChange?.(selected.map((row) => draftFromSaved(row.project as OnScreenProject)));
  }

  function togglePrint(id: string) {
    setPickedPrints((prev) => {
      const next = prev.includes(id)
        ? prev.filter((item) => item !== id)
        : prev.length >= MAX_PRINTS
          ? prev
          : [...prev, id];
      reportPrints(next);
      return next;
    });
  }

  async function saveSetup() {
    const built = projectFromDraft(draft);
    if (typeof built === "string") {
      setSetupNote(built);
      return;
    }
    const name = templateName.trim();
    if (!name) {
      setSetupNote("Name this setup.");
      return;
    }
    setSetupNote("");
    try {
      const saved = await saveOnScreenTemplate(name, built);
      const rows = [saved, ...templates.filter((row) => row.id !== saved.id)];
      setTemplates(rows);
      setTemplateName("");
      setSetupNote("Saved. Check it to print this setup on the next clips.");
    } catch (err) {
      setSetupNote(err instanceof Error ? err.message : "Could not save that setup.");
    }
  }

  async function removeSetup(id: string) {
    try {
      await deleteOnScreenTemplate(id);
    } catch (err) {
      setSetupNote(err instanceof Error ? err.message : "Could not delete that setup.");
      return;
    }
    const rows = templates.filter((row) => row.id !== id);
    setTemplates(rows);
    setPickedPrints((prev) => {
      const next = prev.filter((item) => item !== id);
      reportPrints(next, rows);
      return next;
    });
  }

  function setFit(next: Partial<OnScreenCaption>) {
    onChange({
      ...draft,
      captions: draft.captions.map((cap) => ({ ...cap, ...next })),
    });
  }

  function patchCaption(index: number, next: Partial<OnScreenCaption>) {
    const captions = draft.captions.map((cap, i) => (i === index ? { ...cap, ...next } : cap));
    onChange({ ...draft, captions });
  }

  function lockColor(index: number, boxId: string) {
    const captions = draft.captions.map((cap, i) => {
      const without = cap.box_ids.filter((id) => id !== boxId);
      if (i !== index) return { ...cap, box_ids: without };
      if (cap.box_ids.includes(boxId)) return { ...cap, box_ids: without };
      return { ...cap, box_ids: [...without, boxId] };
    });
    onChange({ ...draft, captions });
  }

  function removeBox(id: string) {
    onChange({
      ...draft,
      boxes: draft.boxes.filter((box) => box.id !== id),
      captions: draft.captions.map((cap) => ({
        ...cap,
        box_ids: cap.box_ids.filter((boxId) => boxId !== id),
      })),
    });
    if (selected === id) setSelected(null);
  }

  function framePoint(event: { clientX: number; clientY: number }) {
    const node = frameRef.current;
    if (!node) return { x: 0, y: 0 };
    return pointInFrame(event, node.getBoundingClientRect());
  }

  function onFramePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    const handle = target.dataset.handle as Handle | undefined;
    const boxId = target.dataset.boxId;
    if (target.dataset.role === "text" && boxId) {
      setSelected(boxId);
      setDrag({ kind: "text", pointerId: event.pointerId, id: boxId });
      event.currentTarget.setPointerCapture?.(event.pointerId);
      return;
    }
    if (handle && boxId) {
      setSelected(boxId);
      setDrag({ kind: "resize", pointerId: event.pointerId, id: boxId, handle });
      event.currentTarget.setPointerCapture?.(event.pointerId);
      return;
    }
    if (boxId) {
      const box = draft.boxes.find((item) => item.id === boxId);
      const point = framePoint(event);
      setSelected(boxId);
      if (box) {
        setDrag({
          kind: "move",
          pointerId: event.pointerId,
          id: boxId,
          dx: point.x - box.x,
          dy: point.y - box.y,
        });
      }
      event.currentTarget.setPointerCapture?.(event.pointerId);
      return;
    }
    if (draft.boxes.length >= 4) return;
    const point = framePoint(event);
    setSelected(null);
    setDrag({ kind: "draw", pointerId: event.pointerId, x0: point.x, y0: point.y, x1: point.x, y1: point.y });
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function onFramePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const point = framePoint(event);
    if (drag.kind === "draw") {
      setDrag({ ...drag, x1: point.x, y1: point.y });
      return;
    }
    if (drag.kind === "text") {
      const box = draft.boxes.find((item) => item.id === drag.id);
      const owner = draft.captions.findIndex((cap) => cap.box_ids.includes(drag.id));
      if (!box || owner < 0 || box.w <= 0 || box.h <= 0) return;
      const x = Math.min(0.92, Math.max(0.08, (point.x - box.x) / box.w));
      const y = Math.min(0.92, Math.max(0.08, (point.y - box.y) / box.h));
      const cap = draft.captions[owner];
      patchCaption(owner, { place: { ...(cap.place || {}), [box.id]: { x, y } } });
      return;
    }
    const box = draft.boxes.find((item) => item.id === drag.id);
    if (!box) return;
    if (drag.kind === "move") {
      const next = clampBox({ ...box, x: point.x - drag.dx, y: point.y - drag.dy });
      onChange({
        ...draft,
        boxes: draft.boxes.map((item) => (item.id === box.id ? { ...item, ...next } : item)),
      });
      return;
    }
    let { x, y, w, h } = box;
    const right = x + w;
    const bottom = y + h;
    if (drag.handle === "nw" || drag.handle === "sw") {
      x = Math.min(point.x, right - MIN_BOX);
      w = right - x;
    } else {
      w = Math.max(MIN_BOX, point.x - x);
    }
    if (drag.handle === "nw" || drag.handle === "ne") {
      y = Math.min(point.y, bottom - MIN_BOX);
      h = bottom - y;
    } else {
      h = Math.max(MIN_BOX, point.y - y);
    }
    const next = clampBox({ x, y, w, h });
    onChange({
      ...draft,
      boxes: draft.boxes.map((item) => (item.id === box.id ? { ...item, ...next } : item)),
    });
  }

  function onFramePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.kind === "draw") {
      const raw = rectFromPoints(drag.x0, drag.y0, drag.x1, drag.y1);
      const color = nextColor(draft.boxes);
      if (color && raw.w >= MIN_BOX && raw.h >= MIN_BOX) {
        const fitted = clampBox(raw);
        onChange({
          ...draft,
          boxes: [...draft.boxes, { id: color.id, color: color.hex, ...fitted }],
          captions: captionsWithNewBox(draft.captions, color.id),
        });
        setSelected(color.id);
      }
    }
    setDrag(null);
  }

  const preview = drag?.kind === "draw" ? rectFromPoints(drag.x0, drag.y0, drag.x1, drag.y1) : null;
  const previewColor = nextColor(draft.boxes);
  const audios = draft.audios || [];
  const activeSound = audios.find((audio) => audio.id === (selectedSound || draft.previewAudio)) || audios[0];

  return (
    <section className="studio-onscreen" data-testid="studio-onscreen" aria-label="On-screen text">
      <label className="studio-option-row studio-caption-toggle">
        <div>
          <div className="studio-option-row__label">On-screen text</div>
          <div className="studio-option-row__hint">Text, sound, and saved setups on this clip. Post captions stay separate.</div>
        </div>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => {
            onEnabledChange(e.target.checked);
            if (e.target.checked) setOpen(true);
          }}
        />
        <span className="studio-switch" data-on={enabled} aria-hidden="true">
          <span className="studio-switch__thumb" />
        </span>
      </label>
      {enabled && !open && (
        <button type="button" className="studio-onscreen__add" onClick={() => setOpen(true)}>
          Edit{draft.boxes.length > 0 ? ` · ${draft.boxes.length}` : ""}
        </button>
      )}
      <Dialog.Root open={enabled && open} onOpenChange={closeEditor}>
        <Dialog.Portal>
          <Dialog.Overlay className="studio-onscreen__overlay" />
          <Dialog.Content className="studio-onscreen__sheet" aria-describedby={undefined}>
            <div className="studio-onscreen__sheet-head">
              <Dialog.Title className="studio-onscreen__title">Edit</Dialog.Title>
              <Dialog.Close className="studio-onscreen__done" type="button">Done</Dialog.Close>
            </div>
            <div className="studio-onscreen__body">
              <div className="studio-onscreen__stage">
                <div className="studio-onscreen__phone-wrap">
                  <div className="studio-onscreen__device">
                    <span className="studio-onscreen__speaker" />
                    <div
                      ref={frameRef}
                      className="studio-onscreen__screen"
                      data-testid="onscreen-phone"
                      data-portrait={aspect.h >= aspect.w}
                      style={{
                        aspectRatio: aspect.css,
                        ["--frame-w" as string]: String(aspect.w),
                        ["--frame-h" as string]: String(aspect.h),
                      }}
                      onPointerDown={onFramePointerDown}
                      onPointerMove={onFramePointerMove}
                      onPointerUp={onFramePointerUp}
                    >
                      {poster ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img className="studio-onscreen__poster" src={poster} alt="" />
                      ) : null}
                      {aspect.h >= aspect.w && (
                      <div className="studio-onscreen__safe" aria-hidden="true">
                        <div className="studio-onscreen__safe-top" style={{ height: `${REEL_SAFE.top * 100}%` }}><span>Header</span></div>
                        <div className="studio-onscreen__safe-right" style={{ top: `${REEL_SAFE.top * 100}%`, bottom: `${REEL_SAFE.bottom * 100}%`, width: `${REEL_SAFE.right * 100}%` }}><span>Buttons</span></div>
                        <div className="studio-onscreen__safe-bottom" style={{ height: `${REEL_SAFE.bottom * 100}%` }}><span>Caption</span></div>
                      </div>
                      )}
                      {draft.boxes.map((box) => {
                        const meta = BOX_COLORS.find((color) => color.id === box.id);
                        const owner = draft.captions.find((cap) => cap.box_ids.includes(box.id));
                        const spot = owner?.place?.[box.id] ?? { x: 0.5, y: 0.5 };
                        const shown = owner?.text
                          ? (draft.look.style === "strong" ? owner.text.toUpperCase() : owner.text)
                          : "";
                        const bar = draft.look.style === "caption-bar";
                        return (
                          <div
                            key={box.id}
                            className="studio-onscreen__box"
                            data-box-id={box.id}
                            data-selected={selected === box.id}
                            style={{
                              left: `${box.x * 100}%`,
                              top: `${box.y * 100}%`,
                              width: `${box.w * 100}%`,
                              height: `${box.h * 100}%`,
                              ["--box" as string]: colorOf(box),
                            }}
                          >
                            {!shown && (
                              <span className="studio-onscreen__box-name" data-box-id={box.id}>{meta?.label || box.id}</span>
                            )}
                            {shown && !bar && (
                              <span
                                className={`studio-onscreen__type studio-onscreen__type--${draft.look.background}`}
                                data-role="text"
                                data-box-id={box.id}
                                data-lines={owner?.lines || undefined}
                                style={{
                                  ...seatStyle(spot.x, spot.y),
                                  fontSize: `calc(6.2cqw * ${owner?.size ?? 1})`,
                                }}
                              >
                                {shown}
                              </span>
                            )}
                            {selected === box.id && HANDLES.map((handle) => (
                              <span
                                key={handle}
                                className={`studio-onscreen__handle studio-onscreen__handle--${handle}`}
                                data-handle={handle}
                                data-box-id={box.id}
                              />
                            ))}
                          </div>
                        );
                      })}
                      {draft.look.style === "caption-bar" && draft.boxes.map((box) => {
                        const owner = draft.captions.find((cap) => cap.box_ids.includes(box.id));
                        const shown = owner?.text || "";
                        if (!shown) return null;
                        const spot = owner?.place?.[box.id] ?? { x: 0.5, y: 0.5 };
                        return (
                          <span
                            key={`bar-${box.id}`}
                            className="studio-onscreen__type studio-onscreen__type--bar"
                            data-role="text"
                            data-box-id={box.id}
                            data-lines={owner?.lines || undefined}
                            style={{
                              top: `${(box.y + spot.y * box.h) * 100}%`,
                              fontSize: `calc(4.2cqw * ${owner?.size ?? 1})`,
                            }}
                          >
                            {shown}
                          </span>
                        );
                      })}
                      {preview && previewColor && preview.w > 0 && preview.h > 0 && (
                        <div
                          className="studio-onscreen__box studio-onscreen__box--draft"
                          style={{
                            left: `${preview.x * 100}%`,
                            top: `${preview.y * 100}%`,
                            width: `${preview.w * 100}%`,
                            height: `${preview.h * 100}%`,
                            ["--box" as string]: previewColor.hex,
                          }}
                        />
                      )}
                    </div>
                  </div>
                </div>
                <div className="studio-onscreen__frames" role="group" aria-label="Frame shape">
                  <button
                    type="button"
                    className="studio-onscreen__clip"
                    data-on={framePreset === null}
                    onClick={() => setFramePreset(null)}
                  >
                    Source
                  </button>
                  {FRAME_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className="studio-onscreen__clip"
                      data-on={framePreset === preset.id}
                      onClick={() => setFramePreset(preset.id)}
                    >
                      {preset.id}
                    </button>
                  ))}
                </div>
                {sources.length > 1 && (
                  <div className="studio-onscreen__clips" role="group" aria-label="Clip preview">
                    {sources.map((source, index) => (
                      <button
                        key={source.key}
                        type="button"
                        className="studio-onscreen__clip"
                        data-on={index === Math.min(clipIndex, sources.length - 1)}
                        onClick={() => setClipIndex(index)}
                      >
                        {source.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="studio-onscreen__panel" role="tabpanel">
                {tool === "text" && (
                  <>
                    <div className="studio-onscreen__looks" role="group" aria-label="Look">
                      {(
                        [
                          ["classic", "Instagram sticker"],
                          ["strong", "Strong"],
                          ["caption-bar", "Snapchat bar"],
                        ] as const
                      ).map(([style, label]) => (
                        <button
                          key={style}
                          type="button"
                          className="studio-onscreen__look"
                          data-on={draft.look.style === style}
                          onClick={() => onChange({ ...draft, look: { ...draft.look, style } })}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    {draft.look.style !== "caption-bar" && (
                      <div className="studio-onscreen__looks" role="group" aria-label="Background">
                        {(
                          [
                            ["solid", "Solid"],
                            ["see-through", "See-through"],
                            ["plain", "No shadow"],
                            ["none", "Shadow"],
                          ] as const
                        ).map(([background, label]) => (
                          <button
                            key={background}
                            type="button"
                            className="studio-onscreen__look"
                            data-on={draft.look.background === background}
                            onClick={() => onChange({ ...draft, look: { ...draft.look, background } })}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="studio-onscreen__fit" role="group" aria-label="Text size">
                      <button type="button" className="studio-onscreen__look" aria-label="Smaller" onClick={() => setFit({ size: clampTextSize((draft.captions[0]?.size ?? 1) - 0.1) })}>Smaller</button>
                      <span>{Math.round((draft.captions[0]?.size ?? 1) * 100)}%</span>
                      <button type="button" className="studio-onscreen__look" aria-label="Larger" onClick={() => setFit({ size: clampTextSize((draft.captions[0]?.size ?? 1) + 0.1) })}>Larger</button>
                      <button type="button" className="studio-onscreen__look" data-on={draft.captions[0]?.lines === 1 || draft.captions[0]?.lines === "both"} aria-pressed={draft.captions[0]?.lines === 1 || draft.captions[0]?.lines === "both"} onClick={() => toggleLine(1)}>1 line</button>
                      <button type="button" className="studio-onscreen__look" data-on={draft.captions[0]?.lines === 2 || draft.captions[0]?.lines === "both"} aria-pressed={draft.captions[0]?.lines === 2 || draft.captions[0]?.lines === "both"} onClick={() => toggleLine(2)}>2 lines</button>
                      <button
                        type="button"
                        className="studio-onscreen__look"
                        data-on={!!draft.chooseSeats}
                        aria-pressed={!!draft.chooseSeats}
                        onClick={() => onChange({ ...draft, chooseSeats: !draft.chooseSeats })}
                      >
                        Choose seats
                      </button>
                    </div>
                    {draft.chooseSeats && draft.boxes.length > 0 && (
                      <div className="studio-onscreen__seats" role="group" aria-label="Seats">
                        {(draft.look.style === "caption-bar" ? TEXT_SEATS.filter((seat) => seat.id === "tc" || seat.id === "mc" || seat.id === "bc") : TEXT_SEATS).map((seat) => {
                          const box = draft.boxes.find((item) => item.id === selected) || draft.boxes[0];
                          const on = !!box?.seats?.includes(seat.id);
                          return (
                            <button
                              key={seat.id}
                              type="button"
                              className="studio-onscreen__look"
                              data-on={on}
                              aria-pressed={on}
                              onClick={() => toggleSeat(seat.id)}
                            >
                              {draft.look.style === "caption-bar" ? (seat.id === "tc" ? "Top" : seat.id === "mc" ? "Middle" : "Bottom") : seat.label}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {fitWarning ? <p className="studio-onscreen__hint" role="status">{fitWarning}</p> : null}
                    <p className="studio-onscreen__hint">
                      {draft.chooseSeats
                        ? "Tap the seats that look right on this clip. One seat keeps every variant there. Two or more take turns."
                        : "Drag the words on the clip. The first variant matches this preview. The others keep that look and move inside the box."}
                      {draft.captions[0]?.lines === "both" ? " This pack uses both a one-line and a two-line version." : ""}
                    </p>
                    <div className="studio-onscreen__lines">
                      {draft.captions.map((cap, index) => (
                        <div key={cap.id} className="studio-onscreen__line" data-testid="studio-onscreen-line">
                          <textarea
                            className="studio-caption-prompt studio-onscreen__prompt"
                            rows={2}
                            maxLength={120}
                            value={cap.text}
                            aria-label={`On-screen line ${index + 1}`}
                            placeholder="Line on the video"
                            style={{ fontSize: 16 }}
                            onChange={(e) => patchCaption(index, { text: e.target.value })}
                          />
                          <div className="studio-onscreen__slots" role="group" aria-label={`Colors for line ${index + 1}`}>
                            {draft.boxes.map((box) => {
                              const meta = BOX_COLORS.find((color) => color.id === box.id);
                              const owner = draft.captions.findIndex((item) => item.box_ids.includes(box.id));
                              if (owner >= 0 && owner !== index) return null;
                              const on = owner === index;
                              const label = meta?.label || box.id;
                              const name = on ? `${label}, this line` : `Add ${label}`;
                              return (
                                <button
                                  key={box.id}
                                  type="button"
                                  className="studio-onscreen__chip"
                                  data-on={on}
                                  data-taken={owner >= 0 && !on}
                                  aria-label={name}
                                  aria-pressed={on}
                                  style={{ ["--box" as string]: colorOf(box) }}
                                  onClick={() => lockColor(index, box.id)}
                                >
                                  <span>{label}</span>
                                </button>
                              );
                            })}
                            {draft.boxes.length === 0 && (
                              <span className="studio-onscreen__hint">Drag a box on the preview. It locks to this line.</span>
                            )}
                          </div>
                        </div>
                      ))}
                      {draft.captions.length < 4 && (
                        <button
                          type="button"
                          className="studio-onscreen__add"
                          onClick={() => onChange({
                            ...draft,
                            captions: [
                              ...draft.captions,
                              { id: String(draft.captions.length + 1), text: "", box_ids: [] },
                            ],
                          })}
                        >
                          Add another line
                        </button>
                      )}
                      {selected && (
                        <button type="button" className="studio-onscreen__add" onClick={() => removeBox(selected)}>
                          Remove {BOX_COLORS.find((color) => color.id === selected)?.label || "box"}
                        </button>
                      )}
                    </div>
                  </>
                )}
                {tool === "sound" && (
                  <>
                    <p className="studio-onscreen__hint">
                      Add up to 4 sounds you are allowed to use. A video works too — only its sound is kept. The pack takes turns. Variant 1 uses the one you play. Under the voice keeps the talking. Replace drops the original audio.
                    </p>
                    <div className="studio-onscreen__looks" role="listbox" aria-label="Sounds">
                      {audios.map((audio) => (
                        <button
                          key={audio.id}
                          type="button"
                          role="option"
                          aria-selected={activeSound?.id === audio.id}
                          className="studio-onscreen__look"
                          data-on={activeSound?.id === audio.id}
                          onClick={() => setSelectedSound(audio.id)}
                        >
                          {audio.name}
                        </button>
                      ))}
                      {audios.length < MAX_SOUNDS && (
                        <button type="button" className="studio-onscreen__look" onClick={() => soundInputRef.current?.click()}>
                          Add a sound
                        </button>
                      )}
                    </div>
                    {activeSound ? (
                      <div className="studio-onscreen__sound" data-testid="studio-onscreen-sound">
                        <div className="studio-onscreen__sound-row">
                          <button type="button" className="studio-onscreen__look" data-on={playing === activeSound.id} onClick={() => playSound(activeSound)}>
                            {playing === activeSound.id ? "Stop" : "Play"}
                          </button>
                          <span className="studio-onscreen__sound-name">{activeSound.name}</span>
                          <button type="button" className="studio-onscreen__look" onClick={() => removeSound(activeSound.id)} aria-label={`Remove ${activeSound.name}`}>
                            Remove
                          </button>
                        </div>
                        <label className="studio-onscreen__volume">
                          Volume {Math.round(activeSound.volume * 100)}%
                          <input
                            type="range"
                            min={0}
                            max={100}
                            value={Math.round(activeSound.volume * 100)}
                            aria-label={`${activeSound.name} volume`}
                            onChange={(event) => patchAudio(activeSound.id, { volume: Number(event.target.value) / 100 })}
                          />
                        </label>
                        <div className="studio-onscreen__fit" role="group" aria-label={`${activeSound.name} mode`}>
                          <button type="button" className="studio-onscreen__look" data-on={activeSound.mode !== "replace"} onClick={() => setSoundMode(activeSound, "under")}>Under the voice</button>
                          <button type="button" className="studio-onscreen__look" data-on={activeSound.mode === "replace"} onClick={() => setSoundMode(activeSound, "replace")}>Replace</button>
                          <label className="studio-onscreen__start">
                            Start
                            <input
                              type="number"
                              min={0}
                              max={30}
                              step={1}
                              value={activeSound.start}
                              aria-label={`${activeSound.name} start`}
                              style={{ fontSize: 16 }}
                              onChange={(event) => patchAudio(activeSound.id, { start: Math.min(30, Math.max(0, Number(event.target.value) || 0)) })}
                            />
                          </label>
                        </div>
                      </div>
                    ) : (
                      <p className="studio-onscreen__hint">Add a sound, or a video that already has the sound you want.</p>
                    )}
                  </>
                )}
                {tool === "setups" && (
                  <>
                    <p className="studio-onscreen__hint">
                      Save a winning box, words, seats, and sounds. Check up to 5 to print them on this clip.
                    </p>
                    <div className="studio-onscreen__sound-row">
                      <input
                        className="studio-onscreen__name"
                        value={templateName}
                        maxLength={48}
                        placeholder="Name this setup"
                        aria-label="Setup name"
                        style={{ fontSize: 16 }}
                        onChange={(event) => setTemplateName(event.target.value)}
                      />
                      <button type="button" className="studio-onscreen__add" onClick={() => void saveSetup()}>Save</button>
                    </div>
                    <div className="studio-onscreen__cards">
                      {templates.map((row) => {
                        const on = pickedPrints.includes(row.id);
                        return (
                          <div key={row.id} className="studio-onscreen__card" data-testid="studio-onscreen-setup">
                            <span className="studio-onscreen__sound-name">{row.name}</span>
                            <button
                              type="button"
                              className="studio-onscreen__look"
                              data-on={on}
                              aria-pressed={on}
                              onClick={() => togglePrint(row.id)}
                            >
                              {on ? "Printing" : "Print"}
                            </button>
                            <button type="button" className="studio-onscreen__look" onClick={() => onChange(draftFromSaved(row.project as OnScreenProject))}>
                              Use
                            </button>
                            <button type="button" className="studio-onscreen__look" aria-label={`Delete ${row.name}`} onClick={() => void removeSetup(row.id)}>
                              Delete
                            </button>
                          </div>
                        );
                      })}
                    </div>
                    {pickedPrints.length > 0 && (
                      <p className="studio-onscreen__hint" data-testid="print-plan">
                        Printing {pickedPrints.length} setups, {printPlan(perVideo, pickedPrints.length).each} variants each ({printPlan(perVideo, pickedPrints.length).total} total).
                      </p>
                    )}
                  </>
                )}
              </div>
              {setupNote ? <p className="studio-onscreen__hint" role="status">{setupNote}</p> : null}
              <input
                ref={soundInputRef}
                className="studio-onscreen__file"
                type="file"
                accept="audio/*,video/*,.mp3,.m4a,.aac,.wav,.ogg,.flac,.mp4,.mov,.m4v,.webm,.mkv,.avi"
                multiple
                aria-label="Add a sound"
                onChange={(event) => {
                  addSounds(event.target.files);
                  event.target.value = "";
                }}
              />
              <div className="studio-onscreen__dock" role="tablist" aria-label="Editor tools">
                {(
                  [
                    ["text", "title", "Text"],
                    ["sound", "music_note", "Sound"],
                    ["setups", "bookmark", "Setups"],
                  ] as const
                ).map(([id, icon, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    className="studio-onscreen__tool"
                    data-on={tool === id}
                    aria-selected={tool === id}
                    onClick={() => setTool(id)}
                  >
                    <span className="material-symbols-rounded" aria-hidden="true">{icon}</span>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
