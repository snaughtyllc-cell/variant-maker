"use client";
import useSWR from "swr";
import { getAuthMe } from "./api";
import type { AuthMe } from "./types";

export function useAuthMe() {
  const { data, mutate, isLoading, error } = useSWR<AuthMe>(
    "/api/auth/me",
    getAuthMe,
    { revalidateOnFocus: true },
  );
  return { data, mutate, isLoading, error };
}
