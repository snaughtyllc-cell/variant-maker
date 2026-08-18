"use client";
import { ReactNode, useRef } from "react";

interface VideoThumbProps {
  src: string;
  badge?: ReactNode;
  className?: string;
}

export function VideoThumb({ src, badge, className }: VideoThumbProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  function handleMouseEnter() {
    const v = videoRef.current;
    if (!v) return;
    v.loop = true;
    v.play().catch(() => {/* autoplay may be blocked; silent fail */});
  }

  function handleMouseLeave() {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    v.currentTime = 0;
  }

  return (
    <div
      className={className}
      style={{
        aspectRatio: "9 / 16",
        borderRadius: 6,
        position: "relative",
        overflow: "hidden",
        background: "#14141d",
        border: "1px solid var(--color-line)",
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <video
        ref={videoRef}
        src={src}
        preload="metadata"
        muted
        playsInline
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />
      {badge && (
        <div
          style={{
            position: "absolute",
            bottom: 3,
            left: 3,
          }}
        >
          {badge}
        </div>
      )}
    </div>
  );
}
