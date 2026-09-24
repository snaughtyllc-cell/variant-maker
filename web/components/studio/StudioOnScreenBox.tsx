"use client";

import { useRef, useState } from "react";

export type OnScreenStyle = "classic" | "strong" | "caption-bar";
export type OnScreenBackground = "solid" | "see-through" | "none";

export type OnScreenCaption = {
  id: string;
  text: string;
  box_ids: string[];
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
const HANDLES = ["nw", "ne", "sw", "se"] as const;

type Handle = (typeof HANDLES)[number];

type Drag =
  | { kind: "draw"; pointerId: number; x0: number; y0: number; x1: number; y1: number }
  | { kind: "move"; pointerId: number; id: string; dx: number; dy: number }
  | { kind: "resize"; pointerId: number; id: string; handle: Handle };

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
    .map((cap, i) => ({
      id: String(i + 1),
      text: cap.text.trim(),
      box_ids: cap.box_ids.filter((id) => known.has(id)),
    }))
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

export function StudioOnScreenBox({
  enabled,
  onEnabledChange,
  draft,
  onChange,
}: {
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  draft: OnScreenProject;
  onChange: (next: OnScreenProject) => void;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);

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
          onChange={(e) => onEnabledChange(e.target.checked)}
        />
        <span className="studio-switch" data-on={enabled} aria-hidden="true">
          <span className="studio-switch__thumb" />
        </span>
      </label>
      {enabled && (
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
              <div
                ref={frameRef}
                className="studio-onscreen__phone"
                data-testid="onscreen-phone"
                onPointerDown={onFramePointerDown}
                onPointerMove={onFramePointerMove}
                onPointerUp={onFramePointerUp}
              >
                <span className="studio-onscreen__notch" />
                {draft.boxes.map((box) => (
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
                    {selected === box.id && HANDLES.map((handle) => (
                      <span
                        key={handle}
                        className={`studio-onscreen__handle studio-onscreen__handle--${handle}`}
                        data-handle={handle}
                        data-box-id={box.id}
                      />
                    ))}
                  </div>
                ))}
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
              <p className="studio-onscreen__hint">
                {draft.boxes.length >= 4
                  ? "Four boxes is the limit. Drag a corner to resize."
                  : "Drag on the phone to draw a box. Drag a corner to resize."}
              </p>
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
                      const on = cap.box_ids.includes(box.id);
                      return (
                        <button
                          key={box.id}
                          type="button"
                          className="studio-onscreen__chip"
                          data-on={on}
                          aria-label={`${meta?.label || box.id} box`}
                          aria-pressed={on}
                          style={{ ["--box" as string]: colorOf(box) }}
                          onClick={() => lockColor(index, box.id)}
                        >
                          <span>{meta?.label || box.id}</span>
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
      )}
    </section>
  );
}
