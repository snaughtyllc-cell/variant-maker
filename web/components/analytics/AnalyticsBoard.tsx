"use client";

import { useEffect, useState } from "react";
import {
  getInstagramAnalytics,
  getInstagramStatus,
  regenerate,
  syncInstagram,
} from "@/lib/api";
import { InstagramPanel } from "@/components/InstagramPanel";
import {
  AMPLIFY_MORE_N,
  galleryViewsCopy,
  handleLabel,
  packViewsCopy,
} from "@/lib/instagram";
import type { InstagramAnalytics, InstagramStatus } from "@/lib/types";

export function AnalyticsBoard() {
  const [status, setStatus] = useState<InstagramStatus | null>(null);
  const [analytics, setAnalytics] = useState<InstagramAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [amplifying, setAmplifying] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function load() {
    try {
      const [nextStatus, nextAnalytics] = await Promise.all([
        getInstagramStatus(),
        getInstagramAnalytics(),
      ]);
      setStatus(nextStatus);
      setAnalytics(nextAnalytics);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Analytics");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    setNote(null);
    try {
      const out = await syncInstagram();
      setAnalytics({
        insights_views: out.analytics.insights_views,
        insights_linked: out.analytics.insights_linked,
        ranked: out.analytics.ranked ?? [],
        accounts: status?.accounts ?? [],
      });
      await load();
      setNote(`Matched ${out.matched} post${out.matched === 1 ? "" : "s"} across ${out.accounts} account${out.accounts === 1 ? "" : "s"}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function handleAmplify(sourceId: string) {
    setAmplifying(sourceId);
    setError(null);
    try {
      await regenerate(sourceId, AMPLIFY_MORE_N);
      setNote(`Generating ${AMPLIFY_MORE_N} more of this original.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate more failed");
    } finally {
      setAmplifying(null);
    }
  }

  const accounts = analytics?.accounts ?? status?.accounts ?? [];
  const ranked = analytics?.ranked ?? [];
  const headline = galleryViewsCopy(
    analytics?.insights_views,
    analytics?.insights_linked ?? 0,
    accounts.length,
  );

  return (
    <div className="analytics-board">
      <div className="analytics-hero">
        <div>
          <p className="drive-eyebrow">Pack performance</p>
          <h2 className="analytics-hero__title">{headline}</h2>
          {accounts.length > 0 && (
            <p className="analytics-hero__accounts">
              {accounts.map((a) => handleLabel(a.username)).join(" · ")}
            </p>
          )}
        </div>
        <button
          type="button"
          className="drive-btn drive-btn--dark"
          onClick={handleSync}
          disabled={syncing || accounts.length === 0}
        >
          {syncing ? "Syncing…" : "Sync insights"}
        </button>
      </div>
      {error && (
        <div className="drive-form-error" role="alert">
          {error}
        </div>
      )}
      {note && (
        <div className="drive-banner" role="status">
          {note}
        </div>
      )}

      <InstagramPanel />

      <section className="drive-card" aria-label="Ranked originals">
        <div className="drive-card__title">Ranked originals</div>
        <p className="drive-card__copy">
          Unit of winning is the source — mint more unique files of the original that is working.
          Unlinked copies are unknown, not zero views.
        </p>
        {ranked.length === 0 ? (
          <div className="drive-table__empty">No linked Reels yet. Connect testers, then Sync insights.</div>
        ) : (
          <div className="analytics-ranked">
            {ranked.map((row, i) => {
              const copies = (row.insights_linked || 0) + (row.insights_unknown || 0);
              const copy = packViewsCopy(row.insights_views, row.insights_linked, copies || row.insights_linked);
              const winner = i === 0 && (row.insights_views || 0) > 0;
              return (
                <div key={row.source_id} className="analytics-ranked__row">
                  <div className="analytics-ranked__main">
                    <div className="analytics-ranked__name" title={row.filename}>
                      {winner ? "Winner · " : ""}
                      {row.filename}
                    </div>
                    <div className="analytics-ranked__meta">{copy}</div>
                  </div>
                  {winner && (
                    <button
                      type="button"
                      className="drive-btn drive-btn--aqua drive-btn--sm"
                      onClick={() => handleAmplify(row.source_id)}
                      disabled={amplifying === row.source_id}
                    >
                      {amplifying === row.source_id
                        ? "Starting…"
                        : `Generate ${AMPLIFY_MORE_N} more of this original`}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
