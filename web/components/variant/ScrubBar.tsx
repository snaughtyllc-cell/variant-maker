"use client";
import { useRef, useState, useCallback, useEffect } from "react";
import { clampTime } from "@/lib/media";
import { formatDuration } from "@/lib/format";

interface ScrubBarProps {
  /**
   * Array of video refs to control. The FIRST ref is the "timeline source" —
   * its currentTime and duration drive the position indicator and time label.
   * All refs are play/pause/seeked together.
   */
  videos: Array<React.RefObject<HTMLVideoElement | null>>;
}

export function ScrubBar({ videos }: ScrubBarProps) {
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const rafRef = useRef<number | null>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const scrubbing = useRef(false);

  const primaryVideo = (): HTMLVideoElement | null => videos[0]?.current ?? null;

  // Read duration from the first video whenever it loads metadata
  useEffect(() => {
    const v = primaryVideo();
    if (!v) return;
    const onMeta = () => setDuration(v.duration || 0);
    v.addEventListener("loadedmetadata", onMeta);
    if (v.duration) setDuration(v.duration);
    return () => v.removeEventListener("loadedmetadata", onMeta);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videos]);

  // RAF loop for time updates while playing
  const startRaf = useCallback(() => {
    const tick = () => {
      const v = primaryVideo();
      if (v) setCurrentTime(v.currentTime);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const stopRaf = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopRaf();
  }, [stopRaf]);

  // Play / pause all videos
  const togglePlayPause = useCallback(() => {
    if (playing) {
      videos.forEach(r => r.current?.pause());
      stopRaf();
      setPlaying(false);
    } else {
      videos.forEach(r => { r.current?.play().catch(() => {}); });
      startRaf();
      setPlaying(true);
    }
  }, [playing, videos, startRaf, stopRaf]);

  // Seek all videos to a fraction of the primary video's duration
  const seekToFraction = useCallback((fraction: number) => {
    const pv = primaryVideo();
    if (!pv) return;
    const targetTime = fraction * pv.duration;
    videos.forEach(r => {
      const v = r.current;
      if (!v) return;
      v.currentTime = clampTime(targetTime, v.duration);
    });
    setCurrentTime(clampTime(targetTime, pv.duration));
  }, [videos]); // eslint-disable-line react-hooks/exhaustive-deps

  const fractionFromEvent = (clientX: number): number => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return 0;
    return Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  };

  const onTrackPointerDown = useCallback((e: React.PointerEvent) => {
    scrubbing.current = true;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    seekToFraction(fractionFromEvent(e.clientX));
  }, [seekToFraction]);

  const onTrackPointerMove = useCallback((e: React.PointerEvent) => {
    if (!scrubbing.current) return;
    seekToFraction(fractionFromEvent(e.clientX));
  }, [seekToFraction]);

  const onTrackPointerUp = useCallback(() => {
    scrubbing.current = false;
  }, []);

  const fraction = duration > 0 ? Math.min(1, currentTime / duration) : 0;
  const pct = fraction * 100;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      {/* Play / Pause button */}
      <button
        onClick={togglePlayPause}
        aria-label={playing ? "Pause" : "Play"}
        style={{
          width: 34,
          height: 34,
          borderRadius: "50%",
          backgroundImage: "var(--background-image-cta)",
          border: "none",
          color: "#fff",
          fontSize: 13,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          flexShrink: 0,
        }}
      >
        {playing ? "⏸" : "▶"}
      </button>

      {/* Progress track */}
      <div
        ref={trackRef}
        style={{
          flex: 1,
          height: 5,
          borderRadius: 99,
          background: "#20202c",
          position: "relative",
          cursor: "pointer",
          touchAction: "none",
        }}
        onPointerDown={onTrackPointerDown}
        onPointerMove={onTrackPointerMove}
        onPointerUp={onTrackPointerUp}
        onPointerCancel={onTrackPointerUp}
      >
        {/* Filled portion */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            borderRadius: 99,
            backgroundImage: "var(--background-image-progress)",
            pointerEvents: "none",
          }}
        />
        {/* Playhead */}
        <div
          style={{
            position: "absolute",
            left: `${pct}%`,
            top: "50%",
            transform: "translate(-50%, -50%)",
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "#fff",
            boxShadow: "0 1px 6px #000",
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Time label */}
      <span
        style={{
          fontSize: 11,
          color: "var(--color-muted)",
          flexShrink: 0,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {formatDuration(currentTime)} / {formatDuration(duration)}
      </span>
    </div>
  );
}
