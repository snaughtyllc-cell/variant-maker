"use client";

export type OnScreenStyle = "classic" | "strong" | "caption-bar";
export type OnScreenBackground = "solid" | "see-through" | "none";

export type OnScreenCaption = {
  id: string;
  text: string;
  box_ids: string[];
};

export type OnScreenProject = {
  captions: OnScreenCaption[];
  boxes: { id: string; x: number; y: number; w: number; h: number }[];
  look: { style: OnScreenStyle; background: OnScreenBackground; color: string };
};

const SLOTS = [
  { id: "top", label: "Top", x: 0.08, y: 0.1, w: 0.84, h: 0.18 },
  { id: "upper", label: "Upper", x: 0.08, y: 0.3, w: 0.84, h: 0.16 },
  { id: "middle", label: "Middle", x: 0.08, y: 0.46, w: 0.84, h: 0.16 },
  { id: "lower", label: "Lower", x: 0.08, y: 0.66, w: 0.84, h: 0.18 },
] as const;

export function emptyOnScreen(): OnScreenProject {
  return {
    captions: [{ id: "1", text: "", box_ids: ["middle"] }],
    boxes: [],
    look: { style: "classic", background: "solid", color: "#FFFFFF" },
  };
}

export function projectFromDraft(draft: OnScreenProject): OnScreenProject | string {
  const captions = draft.captions
    .map((cap, i) => ({
      id: String(i + 1),
      text: cap.text.trim(),
      box_ids: cap.box_ids.filter((id) => SLOTS.some((slot) => slot.id === id)),
    }))
    .filter((cap) => cap.text || cap.box_ids.length);
  if (captions.length === 0) return "Add one on-screen line.";
  if (captions.length > 4) return "At most 4 on-screen lines.";
  if (captions.some((cap) => !cap.text)) return "Each on-screen line needs words.";
  if (captions.some((cap) => cap.box_ids.length === 0)) return "Each line needs a box.";
  const used = captions.flatMap((cap) => cap.box_ids);
  if (new Set(used).size !== used.length) return "Each box locks to one line.";
  if (used.length > 4) return "At most 4 boxes.";
  const boxes = SLOTS.filter((slot) => used.includes(slot.id)).map(({ id, x, y, w, h }) => ({
    id, x, y, w, h,
  }));
  return { captions, boxes, look: draft.look };
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
  function patchCaption(index: number, next: Partial<OnScreenCaption>) {
    const captions = draft.captions.map((cap, i) => (i === index ? { ...cap, ...next } : cap));
    onChange({ ...draft, captions });
  }

  function toggleBox(index: number, slotId: string) {
    const cap = draft.captions[index];
    const has = cap.box_ids.includes(slotId);
    const box_ids = has ? cap.box_ids.filter((id) => id !== slotId) : [...cap.box_ids, slotId];
    patchCaption(index, { box_ids });
  }

  return (
    <section className="studio-onscreen" data-testid="studio-onscreen" aria-label="On-screen text">
      <label className="studio-option-row studio-caption-toggle">
        <div>
          <div className="studio-option-row__label">On-screen text</div>
          <div className="studio-option-row__hint">Burn a line on the finished frame. Post captions stay separate.</div>
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
              <div className="studio-onscreen__slots" role="group" aria-label={`Boxes for line ${index + 1}`}>
                {SLOTS.map((slot) => (
                  <button
                    key={slot.id}
                    type="button"
                    className="studio-onscreen__slot"
                    data-on={cap.box_ids.includes(slot.id)}
                    onClick={() => toggleBox(index, slot.id)}
                  >
                    {slot.label}
                  </button>
                ))}
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
      )}
    </section>
  );
}
