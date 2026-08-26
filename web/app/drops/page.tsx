"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { DropsBoard } from "@/components/drops/DropsBoard";

function DropsContent() {
  const searchParams = useSearchParams();
  return <DropsBoard filter={searchParams.get("filter")} />;
}

export default function DropsPage() {
  return (
    <main className="drops-page">
      <Suspense
        fallback={
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "60px 0",
              color: "var(--color-muted)",
              fontSize: 13,
            }}
          >
            Loading…
          </div>
        }
      >
        <DropsContent />
      </Suspense>
    </main>
  );
}
