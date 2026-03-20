// ── SVG icons matching desktop app (SF Symbols) ─────────────────────────────
// All icons: 20×20 default, stroke-based for crisp rendering

import React from "react";
import Svg, { Path, Line, Circle, Polyline, Rect } from "react-native-svg";

interface IconProps {
  size?: number;
  color?: string;
}

const D = { strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill: "none" };

// square.and.pencil — New Chat
export function IconNewChat({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M12 20H5a2 2 0 01-2-2V5a2 2 0 012-2h13a2 2 0 012 2v5" />
      <Path d="M16.5 15.5l5-5-2-2-5 5V16h2z" />
    </Svg>
  );
}

// person.2 — Agents
export function IconAgents({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="9" cy="7" r="3" />
      <Path d="M3 21v-2a4 4 0 014-4h4a4 4 0 014 4v2" />
      <Circle cx="17" cy="9" r="2.5" />
      <Path d="M21 21v-1.5a3 3 0 00-2.5-2.96" />
    </Svg>
  );
}

// message.fill — Chat
export function IconChat({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </Svg>
  );
}

// clock — History / Schedule
export function IconHistory({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="10" />
      <Polyline points="12 6 12 12 16 14" />
    </Svg>
  );
}

// clock — Cron/Schedule (alias)
export function IconClock({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="10" />
      <Polyline points="12 6 12 12 16 14" />
    </Svg>
  );
}

// gearshape — Settings
export function IconSettings({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="3" />
      <Path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </Svg>
  );
}

// arrow.up — Send (matches desktop exactly)
export function IconSend({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="12" y1="19" x2="12" y2="5" />
      <Polyline points="5 12 12 5 19 12" />
    </Svg>
  );
}

// stop.fill — Stop (filled rect, matches desktop)
export function IconStop({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} strokeWidth={1.8}>
      <Rect x="6" y="6" width="12" height="12" rx="2" fill={color} />
    </Svg>
  );
}

// plus — Add
export function IconPlus({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="12" y1="5" x2="12" y2="19" />
      <Line x1="5" y1="12" x2="19" y2="12" />
    </Svg>
  );
}

// trash — Delete
export function IconTrash({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Polyline points="3 6 5 6 21 6" />
      <Path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
    </Svg>
  );
}

// brain.head.profile — Thinking (with brain folds, matches desktop)
export function IconBrain({ size = 20, color = "#8B5CF6" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 01-2 2h-4a2 2 0 01-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z" />
      <Line x1="9" y1="22" x2="15" y2="22" />
      <Path d="M9 9c1.5 1 2.5 2.5 3 4.5.5-2 1.5-3.5 3-4.5" />
    </Svg>
  );
}

// key — API Keys
export function IconKey({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </Svg>
  );
}

// person.crop.circle — User/Persona
export function IconUser({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <Circle cx="12" cy="7" r="4" />
    </Svg>
  );
}

// person.crop.circle — Persona (matches desktop)
export function IconPerson({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="10" />
      <Circle cx="12" cy="10" r="3" />
      <Path d="M6.168 18.849A4 4 0 0110 16h4a4 4 0 013.834 2.855" />
    </Svg>
  );
}

// server — Server
export function IconServer({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
      <Rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
      <Line x1="6" y1="6" x2="6.01" y2="6" />
      <Line x1="6" y1="18" x2="6.01" y2="18" />
    </Svg>
  );
}

// chevron.right
export function IconChevronRight({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Polyline points="9 18 15 12 9 6" />
    </Svg>
  );
}

// chevron.left
export function IconChevronLeft({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Polyline points="15 18 9 12 15 6" />
    </Svg>
  );
}

// chevron.down
export function IconChevronDown({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Polyline points="6 9 12 15 18 9" />
    </Svg>
  );
}

// moon — Dark mode
export function IconMoon({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </Svg>
  );
}

// sun.max — Light mode
export function IconSun({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="5" />
      <Line x1="12" y1="1" x2="12" y2="3" />
      <Line x1="12" y1="21" x2="12" y2="23" />
      <Line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <Line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <Line x1="1" y1="12" x2="3" y2="12" />
      <Line x1="21" y1="12" x2="23" y2="12" />
      <Line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <Line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </Svg>
  );
}

// desktopcomputer — System/Monitor
export function IconMonitor({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <Line x1="8" y1="21" x2="16" y2="21" />
      <Line x1="12" y1="17" x2="12" y2="21" />
    </Svg>
  );
}

// wifi
export function IconWifi({ size = 20, color = "#34C759" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M5 12.55a11 11 0 0114.08 0" />
      <Path d="M1.42 9a16 16 0 0121.16 0" />
      <Path d="M8.53 16.11a6 6 0 016.95 0" />
      <Line x1="12" y1="20" x2="12.01" y2="20" />
    </Svg>
  );
}

// wifi.slash
export function IconWifiOff({ size = 20, color = "#FF3B30" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="1" y1="1" x2="23" y2="23" />
      <Path d="M16.72 11.06A10.94 10.94 0 0119 12.55" />
      <Path d="M5 12.55a10.94 10.94 0 015.17-2.39" />
      <Path d="M10.71 5.05A16 16 0 0122.56 9" />
      <Path d="M1.42 9a15.91 15.91 0 014.7-2.88" />
      <Path d="M8.53 16.11a6 6 0 016.95 0" />
      <Line x1="12" y1="20" x2="12.01" y2="20" />
    </Svg>
  );
}

// line.3.horizontal — Menu/hamburger
export function IconMenu({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="3" y1="12" x2="21" y2="12" />
      <Line x1="3" y1="6" x2="21" y2="6" />
      <Line x1="3" y1="18" x2="21" y2="18" />
    </Svg>
  );
}

// xmark — Close
export function IconX({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="18" y1="6" x2="6" y2="18" />
      <Line x1="6" y1="6" x2="18" y2="18" />
    </Svg>
  );
}
export { IconX as IconClose };

// folder.fill — Folder (with subtle fill like desktop)
export function IconFolder({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" opacity={0.15} fill={color} />
      <Path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
    </Svg>
  );
}

// folder.badge.plus — New Folder
export function IconNewFolder({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
      <Line x1="12" y1="11" x2="12" y2="17" />
      <Line x1="9" y1="14" x2="15" y2="14" />
    </Svg>
  );
}

// magnifyingglass — Search
export function IconSearch({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="11" cy="11" r="8" />
      <Line x1="21" y1="21" x2="16.65" y2="16.65" />
    </Svg>
  );
}

// arrow.right.square — Logout
export function IconLogout({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <Polyline points="16 17 21 12 16 7" />
      <Line x1="21" y1="12" x2="9" y2="12" />
    </Svg>
  );
}

// pencil — Edit (matches desktop)
export function IconEdit({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </Svg>
  );
}

// doc.on.doc — Copy
export function IconCopy({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <Path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
    </Svg>
  );
}

// checkmark — Success
export function IconCheck({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Polyline points="20 6 9 17 4 12" />
    </Svg>
  );
}

// slider.horizontal.3 — Thinking/Mood
export function IconSliders({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="4" y1="21" x2="4" y2="14" />
      <Line x1="4" y1="10" x2="4" y2="3" />
      <Line x1="12" y1="21" x2="12" y2="12" />
      <Line x1="12" y1="8" x2="12" y2="3" />
      <Line x1="20" y1="21" x2="20" y2="16" />
      <Line x1="20" y1="12" x2="20" y2="3" />
      <Line x1="1" y1="14" x2="7" y2="14" />
      <Line x1="9" y1="8" x2="15" y2="8" />
      <Line x1="17" y1="16" x2="23" y2="16" />
    </Svg>
  );
}

// globe — Web
export function IconGlobe({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="10" />
      <Line x1="2" y1="12" x2="22" y2="12" />
      <Path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </Svg>
  );
}

// bolt.fill — Zap
export function IconZap({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D} fill={color}>
      <Path d="M13 2L3 14h9l-1 10 10-12h-9l1-10z" />
    </Svg>
  );
}

// code — Coding / Engineering
export function IconCode({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Polyline points="16 18 22 12 16 6" />
      <Polyline points="8 6 2 12 8 18" />
    </Svg>
  );
}

// photo — Image
export function IconImage({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <Circle cx="8.5" cy="8.5" r="1.5" />
      <Polyline points="21 15 16 10 5 21" />
    </Svg>
  );
}

// paperclip — Attach
export function IconPaperclip({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </Svg>
  );
}
export { IconPaperclip as IconAttach };

// ellipsis.vertical
export function IconMoreVertical({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Circle cx="12" cy="12" r="1.5" />
      <Circle cx="12" cy="5" r="1.5" />
      <Circle cx="12" cy="19" r="1.5" />
    </Svg>
  );
}

// cpu — Provider
export function IconCpu({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="4" y="4" width="16" height="16" rx="2" />
      <Rect x="9" y="9" width="6" height="6" rx="1" />
      <Line x1="9" y1="1" x2="9" y2="4" /><Line x1="15" y1="1" x2="15" y2="4" />
      <Line x1="9" y1="20" x2="9" y2="23" /><Line x1="15" y1="20" x2="15" y2="23" />
      <Line x1="20" y1="9" x2="23" y2="9" /><Line x1="20" y1="15" x2="23" y2="15" />
      <Line x1="1" y1="9" x2="4" y2="9" /><Line x1="1" y1="15" x2="4" y2="15" />
    </Svg>
  );
}

// puzzlepiece.extension — Skills
export function IconPuzzle({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 01-.837.276c-.47-.07-.802-.48-.968-.925a2.501 2.501 0 10-3.214 3.214c.446.166.855.497.925.968a.979.979 0 01-.276.837l-1.611 1.611a2.404 2.404 0 01-1.704.706 2.402 2.402 0 01-1.704-.706l-1.568-1.568a1.026 1.026 0 00-.877-.29c-.493.074-.84.504-1.02.968a2.5 2.5 0 11-3.237-3.237c.464-.18.894-.527.967-1.02a1.026 1.026 0 00-.289-.877l-1.568-1.568A2.402 2.402 0 011.998 12c0-.617.236-1.234.706-1.704L4.23 8.77c.24-.24.581-.353.917-.303.515.077.877.528 1.073 1.01a2.5 2.5 0 103.259-3.259c-.482-.196-.933-.558-1.01-1.073-.05-.336.062-.676.303-.917l1.525-1.525A2.402 2.402 0 0112 2c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.878.29.493-.074.84-.504 1.02-.968a2.5 2.5 0 113.237 3.237c-.464.18-.894.527-.967 1.02z" />
    </Svg>
  );
}

// link — Channels
export function IconLink({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
      <Path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
    </Svg>
  );
}

// info.circle — About
export function IconInfo({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="10" />
      <Line x1="12" y1="16" x2="12" y2="12" />
      <Line x1="12" y1="8" x2="12.01" y2="8" />
    </Svg>
  );
}

// antenna.radiowaves — Network/Tailscale
export function IconAntenna({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M5 12.55a11 11 0 0114.08 0" />
      <Path d="M8.53 16.11a6 6 0 016.95 0" />
      <Circle cx="12" cy="20" r="1" fill={color} />
    </Svg>
  );
}

// hand.raised — Permissions
export function IconHand({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M18 11V6a2 2 0 00-4 0v1M14 7V4a2 2 0 00-4 0v6M10 5V3a2 2 0 00-4 0v9" />
      <Path d="M6 12v-1a2 2 0 00-4 0v4a8 8 0 0016 0v-5a2 2 0 00-4 0" />
    </Svg>
  );
}

// exclamationmark.triangle — Warning
export function IconWarning({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <Line x1="12" y1="9" x2="12" y2="13" />
      <Line x1="12" y1="17" x2="12.01" y2="17" />
    </Svg>
  );
}

// memorychip — RAM
export function IconMemory({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M6 19v2M10 19v2M14 19v2M18 19v2" />
      <Rect x="3" y="7" width="18" height="12" rx="2" />
      <Rect x="7" y="10" width="3" height="6" rx="0.5" />
      <Rect x="14" y="10" width="3" height="6" rx="0.5" />
    </Svg>
  );
}

// smartphone
export function IconPhone({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
      <Line x1="12" y1="18" x2="12.01" y2="18" />
    </Svg>
  );
}

// speaker
export function IconSpeaker({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="4" y="2" width="16" height="20" rx="2" />
      <Circle cx="12" cy="14" r="4" />
      <Line x1="12" y1="6" x2="12.01" y2="6" />
    </Svg>
  );
}

// music.note — Spotify
export function IconMusic({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M9 18V5l12-2v13" />
      <Circle cx="6" cy="18" r="3" />
      <Circle cx="18" cy="16" r="3" />
    </Svg>
  );
}

// book — Learning mode
export function IconBook({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
      <Path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
    </Svg>
  );
}

// pencil.line — Writing / Copywriting
export function IconPen({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </Svg>
  );
}

// chart.bar — Data / Analytics
export function IconChart({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Line x1="18" y1="20" x2="18" y2="10" />
      <Line x1="12" y1="20" x2="12" y2="4" />
      <Line x1="6" y1="20" x2="6" y2="14" />
    </Svg>
  );
}

// target — Marketing / SEO
export function IconTarget({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Circle cx="12" cy="12" r="10" />
      <Circle cx="12" cy="12" r="6" />
      <Circle cx="12" cy="12" r="2" />
    </Svg>
  );
}

// film — Video / After Effects
export function IconFilm({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
      <Line x1="7" y1="2" x2="7" y2="22" />
      <Line x1="17" y1="2" x2="17" y2="22" />
      <Line x1="2" y1="12" x2="22" y2="12" />
      <Line x1="2" y1="7" x2="7" y2="7" />
      <Line x1="2" y1="17" x2="7" y2="17" />
      <Line x1="17" y1="17" x2="22" y2="17" />
      <Line x1="17" y1="7" x2="22" y2="7" />
    </Svg>
  );
}

// note.text — Notion / Notes
export function IconNote({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...D}>
      <Path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <Polyline points="14 2 14 8 20 8" />
      <Line x1="16" y1="13" x2="8" y2="13" />
      <Line x1="16" y1="17" x2="8" y2="17" />
      <Line x1="10" y1="9" x2="8" y2="9" />
    </Svg>
  );
}

// bell — Notifications
export function IconBell({ size = 20, color = "#F0EDE8" }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <Path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </Svg>
  );
}

// ── Agent icon resolver ───────────────────────────────────────────────────────
type AgentIconInfo = { Icon: React.FC<IconProps>; color: string; bg: string };

const AGENT_ICON_MAP: Record<string, AgentIconInfo> = {
  research:    { Icon: IconSearch,  color: "#8B5CF6", bg: "rgba(139,92,246,.12)" },
  engineering: { Icon: IconCode,    color: "#06B6D4", bg: "rgba(6,182,212,.12)" },
  marketing:   { Icon: IconTarget,  color: "#F59E0B", bg: "rgba(245,158,11,.12)" },
  data:        { Icon: IconChart,   color: "#10B981", bg: "rgba(16,185,129,.12)" },
  design:      { Icon: IconFilm,    color: "#EC4899", bg: "rgba(236,72,153,.12)" },
  operations:  { Icon: IconNote,    color: "#6366F1", bg: "rgba(99,102,241,.12)" },
  writing:     { Icon: IconPen,     color: "#F97316", bg: "rgba(249,115,22,.12)" },
};

const AGENT_NAME_HINTS: Record<string, AgentIconInfo> = {
  copywriter:  { Icon: IconPen,     color: "#F97316", bg: "rgba(249,115,22,.12)" },
  librarian:   { Icon: IconBook,    color: "#8B5CF6", bg: "rgba(139,92,246,.12)" },
  seo:         { Icon: IconGlobe,   color: "#F59E0B", bg: "rgba(245,158,11,.12)" },
  notion:      { Icon: IconNote,    color: "#6366F1", bg: "rgba(99,102,241,.12)" },
  competitor:  { Icon: IconSearch,   color: "#EF4444", bg: "rgba(239,68,68,.12)" },
  knowledge:   { Icon: IconBrain,   color: "#A855F7", bg: "rgba(168,85,247,.12)" },
  code:        { Icon: IconCode,    color: "#06B6D4", bg: "rgba(6,182,212,.12)" },
  after:       { Icon: IconFilm,    color: "#EC4899", bg: "rgba(236,72,153,.12)" },
  research:    { Icon: IconSearch,  color: "#8B5CF6", bg: "rgba(139,92,246,.12)" },
  data:        { Icon: IconChart,   color: "#10B981", bg: "rgba(16,185,129,.12)" },
  writing:     { Icon: IconPen,     color: "#F97316", bg: "rgba(249,115,22,.12)" },
  editor:      { Icon: IconPen,     color: "#F97316", bg: "rgba(249,115,22,.12)" },
};

const DEFAULT_AGENT_ICON: AgentIconInfo = { Icon: IconAgents, color: "#94A3B8", bg: "rgba(148,163,184,.12)" };

export function resolveAgentIcon(agent: { name?: string; category?: string }): AgentIconInfo {
  const cat = (agent.category || "").trim().toLowerCase();
  if (cat && AGENT_ICON_MAP[cat]) return AGENT_ICON_MAP[cat];
  const name = (agent.name || "").toLowerCase();
  for (const [hint, info] of Object.entries(AGENT_NAME_HINTS)) {
    if (name.includes(hint)) return info;
  }
  return DEFAULT_AGENT_ICON;
}
