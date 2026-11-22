export interface CategoryColorDef {
  id: string;
  name: string;
  dotClass: string;
  badgeBg: string;
  badgeBorder: string;
  badgeText: string;
}

export const CATEGORY_COLORS: CategoryColorDef[] = [
  {
    id: "amberGold",
    name: "Amber Gold",
    dotClass: "bg-amber-400",
    badgeBg: "bg-amber-400/10",
    badgeBorder: "border-amber-400/25",
    badgeText: "text-amber-300",
  },
  {
    id: "cyanHub",
    name: "Cyan",
    dotClass: "bg-cyan-400",
    badgeBg: "bg-cyan-400/10",
    badgeBorder: "border-cyan-400/25",
    badgeText: "text-cyan-300",
  },
  {
    id: "teal",
    name: "Teal",
    dotClass: "bg-teal-400",
    badgeBg: "bg-teal-400/10",
    badgeBorder: "border-teal-400/25",
    badgeText: "text-teal-300",
  },
  {
    id: "purpleLock",
    name: "Purple",
    dotClass: "bg-purple-400",
    badgeBg: "bg-purple-400/10",
    badgeBorder: "border-purple-400/25",
    badgeText: "text-purple-300",
  },
  {
    id: "coralFall",
    name: "Coral",
    dotClass: "bg-rose-400",
    badgeBg: "bg-rose-400/10",
    badgeBorder: "border-rose-400/25",
    badgeText: "text-rose-300",
  },
  {
    id: "mintRise",
    name: "Emerald",
    dotClass: "bg-emerald-400",
    badgeBg: "bg-emerald-400/10",
    badgeBorder: "border-emerald-400/25",
    badgeText: "text-emerald-300",
  },
];

export function getCategoryColorDef(colorKey?: string | null): CategoryColorDef {
  if (!colorKey) {
    return {
      id: "slateText",
      name: "Muted Slate",
      dotClass: "bg-luma-smoke",
      badgeBg: "bg-white/[0.06]",
      badgeBorder: "border-white/[0.12]",
      badgeText: "text-luma-secondary",
    };
  }

  const found = CATEGORY_COLORS.find(
    (c) => c.id.toLowerCase() === colorKey.toLowerCase()
  );
  if (found) return found;

  if (colorKey.toLowerCase() === "pink") {
    return {
      id: "pink",
      name: "Pink",
      dotClass: "bg-pink-400",
      badgeBg: "bg-pink-400/10",
      badgeBorder: "border-pink-400/25",
      badgeText: "text-pink-300",
    };
  }

  return {
    id: "slateText",
    name: "Muted Slate",
    dotClass: "bg-luma-smoke",
    badgeBg: "bg-white/[0.06]",
    badgeBorder: "border-white/[0.12]",
    badgeText: "text-luma-secondary",
  };
}

export function getCategoryBadgeClasses(colorKey?: string | null): string {
  const def = getCategoryColorDef(colorKey);
  return `${def.badgeBg} ${def.badgeBorder} ${def.badgeText}`;
}
