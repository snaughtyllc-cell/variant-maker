"use client";
import {
  captionToggleHint,
  captionToggleLabel,
  captionToggleSectionLabel,
} from "@/lib/prepareCopy";

interface CaptionToggleProps {
  checked: boolean;
  onChange: (value: boolean) => void;
}

export function CaptionToggle({ checked, onChange }: CaptionToggleProps) {
  const heading = captionToggleSectionLabel();
  return (
    <section className="studio-caption-section" aria-labelledby="studio-caption-heading">
      <p id="studio-caption-heading" className="studio-stepper__label">
        {heading}
      </p>
      <label className="studio-caption-toggle">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span>
          {captionToggleLabel()}
          <small>{captionToggleHint()}</small>
        </span>
      </label>
    </section>
  );
}
