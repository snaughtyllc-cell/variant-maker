"use client";
import useSWR from "swr";
import { getGallery } from "./api";
import { SourceOut } from "./types";

export function useGallery() {
  const { data, mutate, isLoading } = useSWR<SourceOut[]>(
    "/api/gallery",
    getGallery,
    { revalidateOnFocus: true }
  );
  return { data, mutate, isLoading };
}
