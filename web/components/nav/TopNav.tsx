"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout, setAdminView } from "@/lib/api";
import { useAuthMe } from "@/lib/useAuthMe";
import { showDiagnosticsNav, showTeamNav } from "@/lib/navAccess";
import { EXTRA_TABS, PRIMARY_TABS } from "@/lib/studioDestinations";
import { StatusStrip } from "./StatusStrip";

function extraTabVisible(
  href: string,
  me: { auth_required?: boolean; is_admin?: boolean; role?: string | null } | undefined,
): boolean {
  if (href === "/diagnostics") return showDiagnosticsNav(me);
  if (href === "/team") return showTeamNav(me);
  if (href === "/admin") return Boolean(me?.is_admin);
  return false;
}

function linkActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
}

const linkClass =
  "text-[13px] px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-lg no-underline transition-colors whitespace-nowrap shrink-0";

export function TopNav() {
  const pathname = usePathname();
  const { data: me } = useAuthMe();
  const [moreOpen, setMoreOpen] = useState(false);

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  async function handleExitView() {
    await setAdminView(null);
    window.location.reload();
  }

  const extraLinks = (
    <>
      {EXTRA_TABS.filter((tab) => extraTabVisible(tab.href, me)).map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          className={linkClass}
          style={
            linkActive(pathname, tab.href)
              ? { color: "#ffffff", background: "#1b1b27" }
              : { color: "#8a8aa0" }
          }
        >
          {tab.label}
        </Link>
      ))}
    </>
  );

  return (
    <>
      <header
        className="top-nav flex items-center gap-2 px-3 py-2 border-b border-line sm:gap-[18px] sm:px-[18px] sm:py-3"
        style={{ background: "linear-gradient(180deg, #101018, #0c0c12)" }}
      >
        <div className="top-nav__brand hidden sm:flex items-center gap-2 font-extrabold text-[15px] tracking-[0.2px] text-text shrink-0">
          VaryForge
        </div>

        <nav className="top-nav__links hidden sm:flex gap-1 ml-0 sm:ml-2 min-w-0">
          {PRIMARY_TABS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={linkClass}
              style={
                linkActive(pathname, href)
                  ? { color: "#ffffff", background: "#1b1b27" }
                  : { color: "#8a8aa0" }
              }
            >
              {label}
            </Link>
          ))}
          {extraLinks}
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
                className="top-nav__logout hidden sm:inline text-[12px] font-semibold px-2.5 py-1.5 rounded-lg"
                style={{
                  color: "#ececf4",
                  background: "#1b1b27",
                  border: "1px solid #23232f",
                  cursor: "pointer",
                }}
              >
                Log out
              </button>
              <button
                type="button"
                aria-expanded={moreOpen}
                aria-label="More"
                className="top-nav__more sm:hidden text-[12px] font-semibold px-2.5 py-1.5 rounded-lg"
                style={{
                  color: "#ececf4",
                  background: "#1b1b27",
                  border: "1px solid #23232f",
                  cursor: "pointer",
                }}
                onClick={() => setMoreOpen((o) => !o)}
              >
                More
              </button>
            </>
          )}
        </div>
      </header>
      {moreOpen && me?.email && (
        <div
          className="sm:hidden px-3 py-2 border-b border-line flex flex-col gap-1"
          style={{ background: "#101018" }}
        >
          {me.email && (
            <div className="text-[11.5px] text-muted truncate px-1 py-1">{me.email}</div>
          )}
          <div className="flex flex-wrap gap-1">{extraLinks}</div>
          <button
            type="button"
            onClick={handleLogout}
            className="text-[12px] font-semibold px-2.5 py-2 rounded-lg text-left"
            style={{
              color: "#ececf4",
              background: "#1b1b27",
              border: "1px solid #23232f",
              cursor: "pointer",
            }}
          >
            Log out
          </button>
        </div>
      )}
      {me?.viewing_other && (
        <div
          className="flex items-center gap-3 px-3 py-2 sm:px-[18px] text-[13px]"
          style={{ background: "#1a1610", borderBottom: "1px solid #3a3020", color: "#ffd08a" }}
        >
          <span>Viewing {me.workspace_name || "another studio"} — Exit to your studio</span>
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
      <nav className="app-tab-bar" aria-label="Primary">
        {PRIMARY_TABS.map((item) => {
          const active = linkActive(pathname, item.href);
          const tabLabel = item.short ?? item.label;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-label={item.label}
              aria-current={active ? "page" : undefined}
              className="app-tab-bar__item no-underline"
              style={{ color: active ? "#ffffff" : "#8a8aa0" }}
            >
              {tabLabel}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
