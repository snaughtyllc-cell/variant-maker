"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import { paintVideoFrame, videoFrameSrc } from "@/lib/media";

interface VideoThumbProps {
  src: string;
  badge?: ReactNode;
  className?: string;
}

export function VideoThumb({ src, badge, className }: VideoThumbProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) setInView(e.isIntersecting);
      },
      { rootMargin: "120px", threshold: 0.01 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

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
  }

  return (
    <div
      ref={boxRef}
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
      {inView && (
        <video
          ref={videoRef}
          src={videoFrameSrc(src)}
          preload="metadata"
          muted
          playsInline
          onLoadedMetadata={() => paintVideoFrame(videoRef.current)}
          onLoadedData={() => paintVideoFrame(videoRef.current)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            display: "block",
          }}
        />
      )}
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
