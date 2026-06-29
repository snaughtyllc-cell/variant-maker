"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { StatusStrip } from "./StatusStrip";

const NAV_LINKS = [
  { href: "/", label: "Studio" },
  { href: "/gallery", label: "Gallery" },
  { href: "/diagnostics", label: "Diagnostics" },
] as const;

export function TopNav() {
  const pathname = usePathname();

  return (
    <header
      className="flex items-center gap-[18px] px-[18px] py-3 border-b border-line"
      style={{ background: "linear-gradient(180deg, #101018, #0c0c12)" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 font-extrabold text-[15px] tracking-[0.2px] text-text">
        <span
          className="w-[18px] h-[18px] rounded-[6px] inline-block flex-none"
          style={{
            background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
            boxShadow: "0 0 12px #7c5cff66",
          }}
        />
        Variant Studio
      </div>

      {/* Nav links */}
      <nav className="flex gap-1 ml-2">
        {NAV_LINKS.map(({ href, label }) => {
          const active =
            href === "/"
              ? pathname === "/"
              : pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className="text-[13px] px-3 py-1.5 rounded-lg no-underline transition-colors"
              style={
                active
                  ? { color: "#ffffff", background: "#1b1b27" }
                  : { color: "#8a8aa0" }
              }
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Status pills — push to right */}
      <div className="ml-auto">
        <StatusStrip />
      </div>
    </header>
  );
}
