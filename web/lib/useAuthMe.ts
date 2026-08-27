"use client";
import useSWR from "swr";
import { getAuthMe } from "./api";
import { PAGE_SWR } from "./swrCache";
import type { AuthMe } from "./types";

export function useAuthMe() {
  const { data, mutate, isLoading, error } = useSWR<AuthMe>(
    "/api/auth/me",
    getAuthMe,
    PAGE_SWR,
  );
  return { data, mutate, isLoading, error };
}
