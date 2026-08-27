"use client";
import { totalVariants } from "@/lib/files";
import { MAX_PER_VIDEO, SPEED_TEST_PER_VIDEO, variantStepperHint } from "@/lib/variantStepperCopy";

interface VariantStepperProps {
  value: number;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
  fileCount: number;
  qualityMode?: "fast" | "hq";
}

export function VariantStepper({
  value,
  onChange,
  min = 1,
  max = MAX_PER_VIDEO,
  fileCount,
  qualityMode = "fast",
}: VariantStepperProps) {
  const total = totalVariants(fileCount, value);
  const hint = variantStepperHint(qualityMode);
  const presets: Array<{ value: number; label: string }> = [
    { value: SPEED_TEST_PER_VIDEO, label: `${SPEED_TEST_PER_VIDEO} · speed test` },
    { value: 10, label: "10" },
    { value: 20, label: "20 · usual" },
  ];

  function decrement() {
    if (value > min) onChange(value - 1);
  }
  function increment() {
    if (value < max) onChange(value + 1);
  }
  function setPreset(preset: number) {
    onChange(Math.min(max, Math.max(min, preset)));
  }

  return (
    <div className="studio-stepper">
      <div className="studio-stepper__count">
        <div className="studio-stepper__value">{value}</div>
        <div className="studio-stepper__unit">each</div>
      </div>
      <div className="studio-stepper__btns">
        <button
          type="button"
          className="studio-stepper__btn"
          onClick={decrement}
          disabled={value <= min}
          aria-label="Decrease variants"
        >
          <span className="material-symbols-rounded" style={{ fontSize: 19 }}>remove</span>
        </button>
        <button
          type="button"
          className="studio-stepper__btn"
          onClick={increment}
          disabled={value >= max}
          aria-label="Increase variants"
        >
          <span className="material-symbols-rounded" style={{ fontSize: 19 }}>add</span>
        </button>
      </div>
      <div className="studio-stepper__presets">
        {presets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            className="studio-stepper__preset"
            data-active={value === preset.value || undefined}
            onClick={() => setPreset(preset.value)}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="studio-stepper__hint">
        {fileCount > 0
          ? `per video · ${fileCount} clip${fileCount !== 1 ? "s" : ""} → ${total} total`
          : "per video · add clips above"}
        {hint ? ` · ${hint}` : ""}
      </div>
    </div>
  );
}
