import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useJobProgress } from "@/lib/useJobProgress";

class MockES {
  static last: MockES | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  closed = false;
  constructor(public url: string) { MockES.last = this; }
  close() { this.closed = true; }
  emit(obj: unknown) { this.onmessage?.({ data: JSON.stringify(obj) }); }
}
beforeEach(() => { (globalThis as any).EventSource = MockES as any; MockES.last = null; });

describe("useJobProgress", () => {
  const sources = [{ source_id: "s1", filename: "a.mp4", requested: 1 }];
  it("reduces streamed events and closes on job-done", () => {
    const { result } = renderHook(() => useJobProgress("j1", sources));
    expect(MockES.last?.url).toBe("/api/jobs/j1/events");
    act(() => { MockES.last!.emit({ source_id: "s1", index: 1, state: "rendering", attempt: 0, max_attempts: 0, status: null, quality: null, filename: null }); });
    expect(result.current.bySource.s1.inFlight?.state).toBe("rendering");
    act(() => { MockES.last!.emit({ source_id: "s1", index: 1, state: "done", attempt: 0, max_attempts: 0, status: "ok", quality: { vmaf: 95, histogram_ok: true, regen_count: 0, passed: true, spatial_vmaf: null, spatial_ok: null }, filename: "v01.mp4" }); });
    expect(result.current.bySource.s1.delivered).toBe(1);
    act(() => { MockES.last!.emit({ state: "job-done" }); });
    expect(result.current.complete).toBe(true);
    expect(MockES.last!.closed).toBe(true);
  });
  it("does nothing when jobId is null", () => {
    renderHook(() => useJobProgress(null, sources));
    expect(MockES.last).toBeNull();
  });
  it("waits until sources are known before opening", () => {
    renderHook(() => useJobProgress("j1", []));
    expect(MockES.last).toBeNull();
  });
});
