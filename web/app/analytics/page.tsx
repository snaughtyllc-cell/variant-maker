import { AnalyticsBoard } from "@/components/analytics/AnalyticsBoard";

export default function AnalyticsPage() {
  return (
    <main className="analytics-shell">
      <div className="drive-topbar">
        <span className="drive-topbar__section">ANALYTICS</span>
        <span className="drive-topbar__sep">/</span>
        <span className="drive-topbar__crumb">Pack performance</span>
      </div>
      <div className="drive-scroll">
        <div className="analytics-body">
          <div className="drive-head">
            <p className="drive-head__eyebrow">Track</p>
            <h1 className="drive-head__title">Analytics</h1>
          </div>
          <AnalyticsBoard />
        </div>
      </div>
    </main>
  );
}
