"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Cloud,
  FolderOpen,
  GalleryHorizontalEnd,
  LogOut,
  MoreHorizontal,
  PackageCheck,
  Settings2,
  ShieldCheck,
  UsersRound,
  Workflow,
} from "lucide-react";
import { logout, setAdminView } from "@/lib/api";
import { useAuthMe } from "@/lib/useAuthMe";
import { extraTabVisible, linkActive, visiblePrimaryTabs } from "@/lib/navAccess";
import { EXTRA_TABS, STUDIO_DESTINATIONS } from "@/lib/studioDestinations";
import { StatusStrip } from "./StatusStrip";
import { VarimoMark } from "../brand/VarimoMark";
import { VarimoWordmark } from "../brand/VarimoWordmark";

const ICONS = {
  "/": GalleryHorizontalEnd,
  "/gallery": FolderOpen,
  "/drops": PackageCheck,
  "/workflows": Workflow,
  "/settings/drive": Cloud,
  "/team": UsersRound,
  "/admin": ShieldCheck,
  "/diagnostics": Settings2,
} as const;

// Destinations that get a header breadcrumb — everything except /login (tab: "none").
const SECTION_DESTINATIONS = STUDIO_DESTINATIONS.filter((d) => d.tab !== "none");

export function TopNav() {
  const pathname = usePathname();
  const { data: me } = useAuthMe();
  const [moreOpen, setMoreOpen] = useState(false);
  const allowedExtras = EXTRA_TABS.filter((tab) => extraTabVisible(tab.href, me));
  const primaryTabs = visiblePrimaryTabs(me);
  const section = SECTION_DESTINATIONS.find((d) => linkActive(pathname, d.href));
  const isStudio = pathname === "/";

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
      {/* Desktop header (58px) — nav itself now lives in the SideNav rail.
          Studio ("/") gets the mock breadcrumb + search + GPU chip; every other
          route keeps the section label + StatusStrip it had before. */}
      <header className="vf-header">
        {isStudio ? (
          <>
            <span className="vf-header-section">STUDIO</span>
            <span className="vf-header-crumb-sep">/</span>
            <span className="vf-header-crumb">New pack</span>
            <div className="vf-header-spacer" />
            <div className="vf-header-search" aria-hidden="true">
              <span className="material-symbols-rounded">search</span>
              <span>Search packs, drops, folders</span>
            </div>
            <div className="vf-header-gpu">
              <span className="vf-header-gpu__dot" />
              <span className="vf-header-gpu__label">GPU FREE</span>
            </div>
          </>
        ) : (
          <>
            <span className="vf-header-section">{section ? section.label.toUpperCase() : ""}</span>
            <div className="vf-header-spacer" />
            <StatusStrip />
          </>
        )}
      </header>

      {/* Phone top bar — unchanged below the desktop breakpoint. */}
      <header className="vf-topbar">
        <Link className="vf-brand" href="/" aria-label="varimo Studio home">
          <VarimoMark className="vf-brand-mark" size={22} />
          <VarimoWordmark className="vf-brand-wordmark" />
        </Link>

        <div className="vf-topbar-actions">
          <StatusStrip />
          {(me?.email || allowedExtras.length > 0) && (
            <button
              type="button"
              className="vf-more-trigger"
              aria-expanded={moreOpen}
              aria-controls="vf-mobile-more"
              onClick={() => setMoreOpen((open) => !open)}
            >
              <MoreHorizontal size={17} /> More
            </button>
          )}
        </div>
      </header>

      {moreOpen && (me?.email || allowedExtras.length > 0) && (
        <aside className="vf-mobile-more" id="vf-mobile-more" aria-label="More navigation">
          {me?.email && <span className="vf-mobile-email">{me.email}</span>}
          {allowedExtras.length > 0 && (
            <nav className="vf-mobile-extra-links">
              {allowedExtras.map(({ href, label }) => {
                const Icon = ICONS[href as keyof typeof ICONS];
                return <Link key={href} href={href} onClick={() => setMoreOpen(false)}><Icon size={16} /> {label}</Link>;
              })}
            </nav>
          )}
          {me?.email && <button type="button" className="vf-mobile-logout" onClick={handleLogout}><LogOut size={15} /> Log out</button>}
        </aside>
      )}

      {me?.viewing_other && (
        <div className="vf-viewing-banner">
          <span>Viewing {me.workspace_name || "another studio"}</span>
          <button type="button" onClick={handleExitView}>Exit to my studio</button>
        </div>
      )}

      <nav className="vf-mobile-tabs" data-count={primaryTabs.length} aria-label="Primary navigation">
        {primaryTabs.map((item) => {
          const Icon = ICONS[item.href as keyof typeof ICONS];
          const active = linkActive(pathname, item.href);
          return (
            <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} data-active={active}>
              <Icon size={17} strokeWidth={1.8} />
              <span>{item.short ?? item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
