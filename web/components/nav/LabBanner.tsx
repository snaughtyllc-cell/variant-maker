"use client";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

export function LabBanner() {
  const [lab, setLab] = useState(false);
  useEffect(() => {
    let alive = true;
    getHealth()
      .then((h) => {
        if (alive) setLab(Boolean(h.lab));
      })
      .catch(() => {
        if (alive) setLab(false);
      });
    return () => {
      alive = false;
    };
  }, []);
  if (!lab) return null;
  return (
    <div
      role="status"
      className="px-3 py-2 sm:px-[18px] text-[13px] font-semibold"
      style={{ background: "#2a1810", borderBottom: "1px solid #5a3020", color: "#ffc48a" }}
    >
      LAB — experiments only. Team Studio is the live URL and is not this box.
    </div>
  );
}
