"use client";
import useSWR from "swr";
import { getAuthMe } from "./api";
import type { AuthMe } from "./types";

export function useAuthMe() {
  const { data, mutate, isLoading, error } = useSWR<AuthMe>(
    "/api/auth/me",
    getAuthMe,
    {
      revalidateOnFocus: true,
      refreshInterval: (latest) => (latest?.usage && !latest.usage.uncapped ? 4000 : 0),
    },
  );
  return { data, mutate, isLoading, error };
}
