"use client";
import useSWR from "swr";
import { getDiagnostics } from "./api";
import { DiagnosticsItem } from "./types";

export function useDiagnostics() {
  const { data, mutate, isLoading } = useSWR<DiagnosticsItem[]>(
    "/api/diagnostics",
    getDiagnostics,
    { revalidateOnFocus: true }
  );
  return { data, mutate, isLoading };
}
