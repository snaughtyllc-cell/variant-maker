"use client";
import useSWR from "swr";
import { getGallery } from "./api";
import { PAGE_SWR } from "./swrCache";
import { SourceOut } from "./types";

export function useGallery() {
  const { data, mutate, isLoading } = useSWR<SourceOut[]>(
    "/api/gallery",
    getGallery,
    PAGE_SWR,
  );
  return { data, mutate, isLoading };
}
