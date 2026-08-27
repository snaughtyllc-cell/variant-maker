"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import { cssAspectRatio, DEFAULT_CSS_ASPECT, paintVideoFrame, videoFrameSrc } from "@/lib/media";

interface VideoThumbProps {
  src: string;
  poster?: string;
  badge?: ReactNode;
  className?: string;
}

export function VideoThumb({ src, poster, badge, className }: VideoThumbProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const still = (poster || "").trim();
  const hoveringRef = useRef(false);
  const [inView, setInView] = useState(false);
  const [wantVideo, setWantVideo] = useState(!still);
  const [aspect, setAspect] = useState(DEFAULT_CSS_ASPECT);

  function safePlay(video: HTMLVideoElement | null) {
    if (!video) return;
    video.loop = true;
    const play = video.play();
    if (play && typeof play.then === "function") {
      play.catch(() => {/* autoplay may be blocked; silent fail */});
    }
  }

  useEffect(() => {
    setAspect(DEFAULT_CSS_ASPECT);
    setWantVideo(!(poster || "").trim());
  }, [src, poster]);

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

  function applyVideoAspect(video: HTMLVideoElement | null) {
    if (!video) return;
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      setAspect(cssAspectRatio(video.videoWidth, video.videoHeight));
    }
    paintVideoFrame(video);
  }

  function handleMouseEnter() {
    hoveringRef.current = true;
    if (still) setWantVideo(true);
    safePlay(videoRef.current);
  }

  function handleMouseLeave() {
    hoveringRef.current = false;
    videoRef.current?.pause();
  }

  const showVideo = inView && wantVideo;

  useEffect(() => {
    if (!showVideo || !still || !hoveringRef.current) return;
    safePlay(videoRef.current);
  }, [showVideo, still]);

  return (
    <div
      ref={boxRef}
      className={className}
      style={{
        aspectRatio: aspect,
        width: "100%",
        alignSelf: "start",
        borderRadius: 6,
        position: "relative",
        overflow: "hidden",
        background: "#14141d",
        border: "1px solid var(--color-line)",
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {still && (
        <img
          src={still}
          alt=""
          loading="lazy"
          decoding="async"
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
            display: showVideo ? "none" : "block",
          }}
        />
      )}
      {showVideo && (
        <video
          ref={videoRef}
          src={videoFrameSrc(src)}
          poster={still || undefined}
          preload={still ? "none" : "metadata"}
          muted
          playsInline
          onLoadedMetadata={() => applyVideoAspect(videoRef.current)}
          onLoadedData={() => applyVideoAspect(videoRef.current)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
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
