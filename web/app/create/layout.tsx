"use client";
import { CreateProvider } from "@/lib/createStore";

export default function CreateLayout({ children }: { children: React.ReactNode }) {
  return <CreateProvider>{children}</CreateProvider>;
}
