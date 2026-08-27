/** Shared SWR options so tab switches reuse data instead of refetching. */
export const PAGE_SWR = {
  revalidateOnFocus: false,
  dedupingInterval: 15_000,
  keepPreviousData: true,
} as const;
