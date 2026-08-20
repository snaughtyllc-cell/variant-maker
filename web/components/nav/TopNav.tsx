"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout, setAdminView } from "@/lib/api";
import { useAuthMe } from "@/lib/useAuthMe";
import { StatusStrip } from "./StatusStrip";

const NAV_LINKS = [
  { href: "/", label: "Studio" },
  { href: "/gallery", label: "Gallery" },
  { href: "/workflows", label: "Workflows" },
  { href: "/diagnostics", label: "Diagnostics" },
  { href: "/settings/drive", label: "Drive" },
] as const;

export function TopNav() {
  const pathname = usePathname();
  const { data: me } = useAuthMe();

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  async function handleExitView() {
    await setAdminView(null);
    window.location.reload();
  }

  return (
    <>
      <header
        className="top-nav flex items-center gap-2.5 px-3 py-2.5 border-b border-line sm:gap-[18px] sm:px-[18px] sm:py-3"
        style={{ background: "linear-gradient(180deg, #101018, #0c0c12)" }}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 font-extrabold text-[15px] tracking-[0.2px] text-text shrink-0">
          <span
            className="w-[18px] h-[18px] rounded-[6px] inline-block flex-none"
            style={{
              background: "linear-gradient(135deg, #7c5cff, #ff4d8d)",
              boxShadow: "0 0 12px #7c5cff66",
            }}
          />
          <span className="hidden min-[400px]:inline">VaryForge</span>
        </div>

        {/* Nav links */}
        <nav className="top-nav__links flex gap-1 ml-0 sm:ml-2 min-w-0">
          {NAV_LINKS.map(({ href, label }) => {
            const active =
              href === "/"
                ? pathname === "/"
                : pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className="text-[13px] px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-lg no-underline transition-colors whitespace-nowrap shrink-0"
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
          {(me?.role === "owner" || me?.is_admin) && (
            <Link
              href="/team"
              className="text-[13px] px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-lg no-underline transition-colors whitespace-nowrap shrink-0"
              style={
                pathname === "/team" || pathname.startsWith("/team/")
                  ? { color: "#ffffff", background: "#1b1b27" }
                  : { color: "#8a8aa0" }
              }
            >
              Team
            </Link>
          )}
          {me?.is_admin && (
            <Link
              href="/admin"
              className="text-[13px] px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-lg no-underline transition-colors whitespace-nowrap shrink-0"
              style={
                pathname === "/admin" || pathname.startsWith("/admin/")
                  ? { color: "#ffffff", background: "#1b1b27" }
                  : { color: "#8a8aa0" }
              }
            >
              Admin
            </Link>
          )}
        </nav>

        <div className="ml-auto shrink-0 flex items-center gap-2">
          <StatusStrip />
          {me?.email && (
            <>
              <span
                className="hidden sm:inline text-[11.5px] text-muted max-w-[180px] truncate"
                title={me.email}
              >
                {me.email}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="text-[12px] font-semibold px-2.5 py-1.5 rounded-lg"
                style={{
                  color: "#ececf4",
                  background: "#1b1b27",
                  border: "1px solid #23232f",
                  cursor: "pointer",
                }}
              >
                Log out
              </button>
            </>
          )}
        </div>
      </header>
      {me?.viewing_other && (
        <div
          className="flex items-center gap-3 px-3 py-2 sm:px-[18px] text-[13px]"
          style={{ background: "#1a1610", borderBottom: "1px solid #3a3020", color: "#ffd08a" }}
        >
          <span>
            Viewing {me.workspace_name || "another studio"} — Exit to your studio
          </span>
          <span style={{ opacity: 0.5 }}>·</span>
          <button
            type="button"
            onClick={handleExitView}
            className="font-semibold"
            style={{
              color: "#fff",
              background: "#7c5cff",
              border: "none",
              borderRadius: 8,
              padding: "5px 10px",
              cursor: "pointer",
            }}
          >
            Exit
          </button>
        </div>
      )}
    </>
  );
}
