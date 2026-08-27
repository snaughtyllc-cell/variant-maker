"use client";
import useSWR from "swr";
import { getQueue } from "./api";
import { QueueSnapshot } from "./types";

export const EMPTY_QUEUE: QueueSnapshot = { running: 0, fast: 0, hq: 0, jobs: [] };

export function useQueue() {
  const { data, mutate, isLoading } = useSWR<QueueSnapshot>(
    "/api/queue",
    getQueue,
    { refreshInterval: 4000, revalidateOnFocus: false },
  );
  return { data: data ?? EMPTY_QUEUE, mutate, isLoading };
}
