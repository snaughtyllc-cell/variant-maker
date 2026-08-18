"use client";
import useSWR from "swr";
import { getHealth } from "../../lib/api";

export function StatusStrip() {
  const { data, error } = useSWR("/api/health", () => getHealth(), {
    refreshInterval: 10000,
    revalidateOnFocus: false,
  });

  const online = !error && data?.status === "ok";
  const ready = data !== undefined && !error;
  const loading = data === undefined && !error;

  return (
    <div className="flex items-center gap-2.5 text-[11.5px] text-muted">
      {/* Engine status pill */}
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-line"
        style={{ background: "#14141d" }}
      >
        <span
          className="w-[7px] h-[7px] rounded-full flex-none"
          style={
            ready && online
              ? { background: "#22c55e", boxShadow: "0 0 8px #22c55e88" }
              : loading
              ? { background: "#8a8aa0" }
              : { background: "#f87171", boxShadow: "0 0 8px #f8717188" }
          }
        />
        {loading ? "Connecting…" : ready && online ? "Engine ready" : "Engine offline"}
      </span>

      {/* Local mode pill */}
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-line"
        style={{ background: "#14141d" }}
      >
        Local&nbsp;·&nbsp;CPU&nbsp;<strong className="text-text font-semibold">fast</strong>
      </span>
    </div>
  );
}
