"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState, useRef } from "react";
import { captureVideoPoster } from "@/lib/videoPoster";

export type OnScreenStyle = "classic" | "strong" | "caption-bar";
export type OnScreenBackground = "solid" | "see-through" | "none";

export type OnScreenCaption = {
  id: string;
  text: string;
  box_ids: string[];
  place?: Record<string, { x: number; y: number }>;
};

export type OnScreenBox = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
};

export type OnScreenProject = {
  captions: OnScreenCaption[];
  boxes: OnScreenBox[];
  look: { style: OnScreenStyle; background: OnScreenBackground; color: string };
};

export const BOX_COLORS = [
  { id: "cyan", label: "Cyan", hex: "#14b8c4" },
  { id: "amber", label: "Amber", hex: "#e39b12" },
  { id: "pink", label: "Pink", hex: "#e85d8c" },
  { id: "violet", label: "Violet", hex: "#7c5cff" },
] as const;

const MIN_BOX = 0.06;
export const REEL_SAFE = { top: 0.08, bottom: 0.16, right: 0.14 };
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
    look: { style: "classic", background: "solid", color: "#FFFFFF" },
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
    return { id: box.id, ...fitted, color: box.color };
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
      return { id: String(i + 1), text: cap.text.trim(), box_ids, place };
    })
    .filter((cap) => cap.text || cap.box_ids.length);
  if (captions.length === 0) return "Add one on-screen line.";
  if (captions.length > 4) return "At most 4 on-screen lines.";
  if (captions.some((cap) => !cap.text)) return "Each on-screen line needs words.";
  if (captions.some((cap) => cap.box_ids.length === 0)) return "Each line needs a box.";
  const used = captions.flatMap((cap) => cap.box_ids);
  if (new Set(used).size !== used.length) return "Each box locks to one line.";
  if (boxes.some((box) => !used.includes(box.id))) return "Lock every colored box to a line.";
  return {
    captions,
    boxes: boxes.map(({ id, x, y, w, h }) => ({ id, x, y, w, h, color: draft.boxes.find((b) => b.id === id)?.color || id })),
    look: draft.look,
  };
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
};

export function StudioOnScreenBox({
  enabled,
  onEnabledChange,
  draft,
  onChange,
  sources = [],
}: {
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  draft: OnScreenProject;
  onChange: (next: OnScreenProject) => void;
  sources?: OnScreenPreview[];
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [open, setOpen] = useState(enabled);
  const [clipIndex, setClipIndex] = useState(0);
  const [poster, setPoster] = useState("");
  const clip = sources[Math.min(clipIndex, Math.max(0, sources.length - 1))];

  useEffect(() => {
    if (!clip) {
      setPoster("");
      return;
    }
    if (!clip.file) {
      setPoster(clip.src || "");
      return;
    }
    let cancel = false;
    captureVideoPoster(clip.file)
      .then((url) => {
        if (!cancel) setPoster(url);
      })
      .catch(() => {
        if (!cancel) setPoster(clip.src || "");
      });
    return () => {
      cancel = true;
    };
  }, [clip?.key, clip?.file, clip?.src]);

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
        });
        setSelected(color.id);
      }
    }
    setDrag(null);
  }

  const preview = drag?.kind === "draw" ? rectFromPoints(drag.x0, drag.y0, drag.x1, drag.y1) : null;
  const previewColor = nextColor(draft.boxes);

  return (
    <section className="studio-onscreen" data-testid="studio-onscreen" aria-label="On-screen text">
      <label className="studio-option-row studio-caption-toggle">
        <div>
          <div className="studio-option-row__label">On-screen text</div>
          <div className="studio-option-row__hint">Draw boxes on a phone frame. Post captions stay separate.</div>
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
          Edit boxes{draft.boxes.length > 0 ? ` · ${draft.boxes.length}` : ""}
        </button>
      )}
      <Dialog.Root open={enabled && open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="studio-onscreen__overlay" />
          <Dialog.Content className="studio-onscreen__sheet" aria-describedby={undefined}>
            <div className="studio-onscreen__sheet-head">
              <Dialog.Title className="studio-onscreen__title">Place on-screen text</Dialog.Title>
              <Dialog.Close className="studio-onscreen__done" type="button">Done</Dialog.Close>
            </div>
            <div className="studio-onscreen__body">
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
                  ["none", "Text only"],
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
          <div className="studio-onscreen__stage">
            <div className="studio-onscreen__phone-wrap">
              <div className="studio-onscreen__device">
                <span className="studio-onscreen__speaker" />
                <div
                  ref={frameRef}
                  className="studio-onscreen__screen"
                  data-testid="onscreen-phone"
                  onPointerDown={onFramePointerDown}
                  onPointerMove={onFramePointerMove}
                  onPointerUp={onFramePointerUp}
                >
                  {poster ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img className="studio-onscreen__poster" src={poster} alt="" />
                  ) : null}
                  <div className="studio-onscreen__safe" aria-hidden="true">
                    <div className="studio-onscreen__safe-top" style={{ height: `${REEL_SAFE.top * 100}%` }}><span>Header</span></div>
                    <div className="studio-onscreen__safe-right" style={{ top: `${REEL_SAFE.top * 100}%`, bottom: `${REEL_SAFE.bottom * 100}%`, width: `${REEL_SAFE.right * 100}%` }}><span>Buttons</span></div>
                    <div className="studio-onscreen__safe-bottom" style={{ height: `${REEL_SAFE.bottom * 100}%` }}><span>Caption</span></div>
                  </div>
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
                            style={{ left: `${spot.x * 100}%`, top: `${spot.y * 100}%` }}
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
                        style={{ top: `${(box.y + spot.y * box.h) * 100}%` }}
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
              <p className="studio-onscreen__hint">
                {poster
                  ? "Shaded edges are covered on a Reel. Draw in the clear middle."
                  : "Add a clip and its frame shows here. Shaded edges are covered on a Reel."}
              </p>
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
              {selected && (
                <button type="button" className="studio-onscreen__add" onClick={() => removeBox(selected)}>
                  Remove {BOX_COLORS.find((color) => color.id === selected)?.label || "box"}
                </button>
              )}
            </div>
            <div className="studio-onscreen__lines">
              {draft.captions.map((cap, index) => (
                <div key={cap.id} className="studio-onscreen__line" data-testid="studio-onscreen-line">
                  <textarea
                    className="studio-caption-prompt"
                    rows={2}
                    maxLength={120}
                    value={cap.text}
                    aria-label={`On-screen line ${index + 1}`}
                    placeholder="Line on the video"
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
                      <span className="studio-onscreen__hint">Draw a box first, then tap its color here.</span>
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
            </div>
          </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
