// ── SVG icons matching SF Symbols used in Mac app ─────────────────────────────
// All icons: 16×16 default, stroke-based for crisp rendering

import { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

const defaults = (p: P, size = 16) => ({
  width: p.size ?? size,
  height: p.size ?? size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...p,
});

// square.and.pencil — New Chat
export function IconNewChat(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M12 20H5a2 2 0 01-2-2V5a2 2 0 012-2h13a2 2 0 012 2v5" />
      <path d="M16.5 15.5l5-5-2-2-5 5V16h2z" />
    </svg>
  );
}

// person.2 — Agents
export function IconAgents(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="9" cy="7" r="3" />
      <path d="M3 21v-2a4 4 0 014-4h4a4 4 0 014 4v2" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M21 21v-1.5a3 3 0 00-2.5-2.96" />
    </svg>
  );
}

// gearshape — Settings
export function IconSettings(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  );
}

// folder.fill — Folder
export function IconFolder(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" fill="currentColor" opacity={0.15} />
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
    </svg>
  );
}

// folder.badge.plus — New Folder
export function IconNewFolder(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
      <line x1="9" y1="14" x2="15" y2="14" />
    </svg>
  );
}

// chevron.right
export function IconChevronRight(p: P) {
  return <svg {...defaults(p, 10)}><polyline points="9 6 15 12 9 18" /></svg>;
}
// chevron.down
export function IconChevronDown(p: P) {
  return <svg {...defaults(p, 10)}><polyline points="6 9 12 15 18 9" /></svg>;
}

// cpu — Provider
export function IconCpu(p: P) {
  return (
    <svg {...defaults(p)}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" rx="1" />
      <line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="15" x2="23" y2="15" />
      <line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="15" x2="4" y2="15" />
    </svg>
  );
}

// slider.horizontal.3 — Thinking/Mood
export function IconSliders(p: P) {
  return (
    <svg {...defaults(p)}>
      <line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

// brain.head.profile — Thinking
export function IconBrain(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 01-2 2h-4a2 2 0 01-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z" />
      <line x1="9" y1="22" x2="15" y2="22" />
      <path d="M9 9c1.5 1 2.5 2.5 3 4.5.5-2 1.5-3.5 3-4.5" />
    </svg>
  );
}

// book — Learning mode
export function IconBook(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
    </svg>
  );
}

// globe — Web
export function IconGlobe(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </svg>
  );
}

// key — API Keys
export function IconKey(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  );
}

// music.note — Spotify
export function IconMusic(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M9 18V5l12-2v13" />
      <circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" />
    </svg>
  );
}

// puzzlepiece.extension — Skills
export function IconPuzzle(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 01-.837.276c-.47-.07-.802-.48-.968-.925a2.501 2.501 0 10-3.214 3.214c.446.166.855.497.925.968a.979.979 0 01-.276.837l-1.611 1.611a2.404 2.404 0 01-1.704.706 2.402 2.402 0 01-1.704-.706l-1.568-1.568a1.026 1.026 0 00-.877-.29c-.493.074-.84.504-1.02.968a2.5 2.5 0 11-3.237-3.237c.464-.18.894-.527.967-1.02a1.026 1.026 0 00-.289-.877l-1.568-1.568A2.402 2.402 0 011.998 12c0-.617.236-1.234.706-1.704L4.23 8.77c.24-.24.581-.353.917-.303.515.077.877.528 1.073 1.01a2.5 2.5 0 103.259-3.259c-.482-.196-.933-.558-1.01-1.073-.05-.336.062-.676.303-.917l1.525-1.525A2.402 2.402 0 0112 2c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.878.29.493-.074.84-.504 1.02-.968a2.5 2.5 0 113.237 3.237c-.464.18-.894.527-.967 1.02z" />
    </svg>
  );
}

// person.crop.circle — Persona
export function IconPerson(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.168 18.849A4 4 0 0110 16h4a4 4 0 013.834 2.855" />
    </svg>
  );
}

// link — Channels
export function IconLink(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
    </svg>
  );
}

// clock — Schedule / Cron
export function IconClock(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

// antenna.radiowaves — Network/Tailscale
export function IconAntenna(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M5 12.55a11 11 0 0114.08 0" />
      <path d="M8.53 16.11a6 6 0 016.95 0" />
      <circle cx="12" cy="20" r="1" fill="currentColor" />
    </svg>
  );
}

// hand.raised — Permissions
export function IconHand(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M18 11V6a2 2 0 00-4 0v1M14 7V4a2 2 0 00-4 0v6M10 5V3a2 2 0 00-4 0v9" />
      <path d="M6 12v-1a2 2 0 00-4 0v4a8 8 0 0016 0v-5a2 2 0 00-4 0" />
    </svg>
  );
}

// info.circle — About
export function IconInfo(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

// paperclip.circle — Attach
export function IconAttach(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

// doc.on.doc — Copy
export function IconCopy(p: P) {
  return (
    <svg {...defaults(p)}>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
    </svg>
  );
}

// trash — Delete
export function IconTrash(p: P) {
  return (
    <svg {...defaults(p)}>
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
    </svg>
  );
}

// xmark — Close
export function IconClose(p: P) {
  return (
    <svg {...defaults(p)}>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

// arrow.up — Send
export function IconSend(p: P) {
  return (
    <svg {...defaults(p)}>
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  );
}

// stop.fill — Stop
export function IconStop(p: P) {
  return (
    <svg {...defaults(p)}>
      <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
    </svg>
  );
}

// magnifyingglass — Search
export function IconSearch(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

// plus — Add
export function IconPlus(p: P) {
  return (
    <svg {...defaults(p)}>
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

// checkmark — Success
export function IconCheck(p: P) {
  return <svg {...defaults(p)}><polyline points="20 6 9 17 4 12" /></svg>;
}

// exclamationmark.triangle — Warning
export function IconWarning(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

// pencil — Edit
export function IconEdit(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </svg>
  );
}

// sun.max — Light mode
export function IconSun(p: P) {
  return (
    <svg {...defaults(p)}>
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

// moon — Dark mode
export function IconMoon(p: P) {
  return (
    <svg {...defaults(p)}>
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

// desktopcomputer — System theme
export function IconMonitor(p: P) {
  return (
    <svg {...defaults(p)}>
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}
