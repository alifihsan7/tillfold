import React, { forwardRef, type SVGProps } from "react";

export interface IconProps extends SVGProps<SVGSVGElement> { size?: number | string }

// Tillfold's compact line set: one optical grid, square terminals, no ornamental fills.
// Legacy export names keep existing controls and saved goal choices compatible.
function icon(name: string, drawing: React.ReactNode) {
  const Icon = forwardRef<SVGSVGElement, IconProps>(function Icon({ size = 20, className = "", children, ...props }, ref) {
    const labelled = Boolean(props["aria-label"] || props["aria-labelledby"]);
    return <svg ref={ref} xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="square" strokeLinejoin="round"
      aria-hidden={labelled ? undefined : true} role={labelled ? "img" : undefined} focusable="false"
      className={`fold-icon fold-icon--${name} ${className}`} {...props}>{drawing}{children}</svg>;
  });
  Icon.displayName = name;
  return Icon;
}

export const Plus = icon("plus", <path d="M12 5v14M5 12h14" />);
export const X = icon("close", <path d="m6 6 12 12M18 6 6 18" />);
export const Check = icon("check", <path d="m5 12 4 4L19 6" />);
export const ChevronDown = icon("chevron-down", <path d="m6 9 6 6 6-6" />);
export const ChevronLeft = icon("chevron-left", <path d="m15 6-6 6 6 6" />);
export const ChevronRight = icon("chevron-right", <path d="m9 6 6 6-6 6" />);
export const ArrowRight = icon("arrow-right", <path d="M4 12h16m-6-6 6 6-6 6" />);
export const ArrowLeft = icon("arrow-left", <path d="M20 12H4m6-6-6 6 6 6" />);
export const ArrowDown = icon("arrow-down", <path d="M12 4v16m-6-6 6 6 6-6" />);
export const ArrowUpRight = icon("outgoing", <path d="M6 18 18 6M7 6h11v11" />);
export const ArrowDownLeft = icon("incoming", <path d="M18 6 6 18M6 7v11h11" />);
export const ArrowDownRight = icon("arrow-down-right", <path d="m6 6 12 12M7 18h11V7" />);
export const ArrowLeftRight = icon("transfer", <path d="M3 8h17m-4-4 4 4-4 4M21 16H4m4-4-4 4 4 4" />);
export const Search = icon("search", <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5" /></>);
export const Menu = icon("menu", <path d="M4 6h16M4 12h16M4 18h10" />);
export const Pencil = icon("edit", <><path d="m5 15 10-10 4 4L9 19l-5 1 1-5Zm8-8 4 4" /></>);
export const Edit2 = Pencil;
export const Trash2 = icon("delete", <><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5" /></>);
export const Copy = icon("copy", <><rect x="8" y="8" width="12" height="13" rx="1.5" /><path d="M16 8V3H3v13h5" /></>);
export const ExternalLink = icon("external-link", <path d="M13 4h7v7m0-7L10 14m-2-9H4v15h15v-4" />);
export const Download = icon("download", <path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4" />);
export const Upload = icon("upload", <path d="M12 16V4m-4 4 4-4 4 4M4 17v4h16v-4" />);
export const RefreshCw = icon("refresh", <><path d="M20 4v6h-6M4 20v-6h6" /><path d="M20 10a8 8 0 0 0-14-4M4 14a8 8 0 0 0 14 4" /></>);
export const RotateCcw = icon("undo", <><path d="M4 4v6h6" /><path d="M4 10a8 8 0 1 1 1 7" /></>);
export const Loader2 = icon("loading", <path d="M12 4a8 8 0 1 1-8 8" />);
export const Pause = icon("pause", <path d="M8 5v14M16 5v14" />);
export const Play = icon("play", <path d="m8 4 12 8-12 8V4Z" />);
export const Filter = icon("filter", <path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z" />);
export const Eye = icon("visible", <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>);
export const EyeOff = icon("hidden", <><path d="m3 3 18 18M10 5a12 12 0 0 1 12 7 17 17 0 0 1-3 4M6 6a17 17 0 0 0-4 6s4 7 10 7a11 11 0 0 0 4-1M10 10a3 3 0 0 0 4 4" /></>);
export const Info = icon("info", <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7v.1" /></>);
export const AlertCircle = icon("notice", <><circle cx="12" cy="12" r="9" /><path d="M12 7v6M12 17v.1" /></>);
export const AlertTriangle = icon("warning", <><path d="m12 3 10 18H2L12 3ZM12 9v5M12 17v.1" /></>);
export const CheckCircle2 = icon("confirmed", <><rect x="3" y="3" width="18" height="18" rx="3" /><path d="m7 12 3 3 7-7" /></>);
export const Ban = icon("blocked", <><circle cx="12" cy="12" r="9" /><path d="m6 6 12 12" /></>);
export const PlusCircle = Plus;

// Navigation and financial objects use distinct silhouettes, not repeated tiles.
export const LayoutDashboard = icon("overview", <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 9v12M13 13h4M13 17h4" /></>);
export const Receipt = icon("transactions", <path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3Zm4 5h6m-6 4h6" />);
export const WalletCards = icon("budget", <><rect x="3" y="6" width="18" height="15" rx="2" /><path d="M6 6V3h12v3M3 11h18M10 11v10" /></>);
export const Wallet = icon("wallet", <><path d="M4 6V4h14v3M20 11V7H3v14h17v-5" /><path d="M15 11h6v5h-6zM18 13.5v.1" /></>);
export const CreditCard = icon("account", <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18M7 15h4" /></>);
export const Landmark = icon("bank", <path d="m3 8 9-5 9 5H3Zm2 4v6m7-6v6m7-6v6M3 21h18" />);
export const Layers = icon("pockets", <><path d="M3 10h18v11H3zM3 10l9 6 9-6M6 7h12M9 4h6" /></>);
export const BarChart2 = icon("reports", <path d="M3 3v18h18M7 16v-4M12 16V8M17 16V4" />);
export const Target = icon("goal", <><path d="M5 21V3h14l-3 5 3 5H5" /></>);
export const TrendingUp = icon("investment", <path d="m3 17 6-6 4 4 8-10M15 5h6v6" />);
export const Activity = icon("spending-pace", <path d="M3 16h4l3-10 4 14 3-9h4" />);
export const Settings = icon("settings", <><path d="M4 6h4m4 0h8M4 18h8m4 0h4M10 3v6M14 15v6" /><path d="M4 12h12m4 0h1M18 9v6" /></>);
export const Settings2 = Settings;
export const Bell = icon("bill", <><path d="M6 8a6 6 0 0 1 12 0v6l3 3H3l3-3V8ZM10 21h4" /></>);
export const Calendar = icon("calendar", <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18M8 14h2M14 14h2M8 17h2" /></>);
export const Clock = icon("schedule", <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 3" /></>);
export const Coins = icon("assets", <><path d="M4 6c0-4 16-4 16 0s-16 4-16 0Zm0 0v12c0 4 16 4 16 0V6M4 12c0 4 16 4 16 0" /></>);
export const HandCoins = icon("internal-loan", <><path d="M3 20v-7h5l4 3h4l4-4 2 2-6 7H9l-3-1H3ZM8 13l3-3h4v6" /><circle cx="16" cy="5" r="3" /></>);
export const Tag = icon("category", <><path d="M3 3h8l10 10-8 8L3 11V3Z" /><circle cx="7" cy="7" r="1" /></>);
export const FileSpreadsheet = icon("spreadsheet", <><path d="M4 3h11l5 5v13H4V3Zm11 0v5h5M8 12h8M8 16h8M12 12v7" /></>);
export const Link2 = icon("linked", <><path d="m9 15 6-6M8 16l-1 1a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M16 8l1-1a4 4 0 0 1 6 6l-5 5a4 4 0 0 1-6 0" transform="translate(1 1) scale(.9)" /></>);
export const Unlink = icon("unlinked", <path d="m9 15-2 2a4 4 0 0 1-6-6l4-4m10 2 2-2a4 4 0 0 1 6 6l-4 4M3 3l18 18" />);

export const User = icon("profile", <><circle cx="12" cy="7" r="4" /><path d="M4 21v-3a8 6 0 0 1 16 0v3" /></>);
export const UserPlus = icon("register", <><circle cx="9" cy="7" r="4" /><path d="M2 21v-3a7 6 0 0 1 11-5M18 12v8M14 16h8" /></>);
export const LogIn = icon("sign-in", <path d="M14 3h7v18h-7M3 12h12m-5-5 5 5-5 5" />);
export const LogOut = icon("sign-out", <path d="M10 3H3v18h7M9 12h12m-5-5 5 5-5 5" />);
export const Shield = icon("security", <path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z" />);
export const ShieldCheck = icon("savings", <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>);
export const KeyRound = icon("password", <><circle cx="8" cy="8" r="5" /><path d="m12 12 9 9m-4-4 3-3m-6 0 3-3" /></>);
export const AtSign = icon("email", <><circle cx="12" cy="12" r="4" /><path d="M16 8v7c0 3 5 2 5-3a9 9 0 1 0-4 7" /></>);
export const Bot = icon("telegram-bot", <><path d="M3 4h18v13H9l-6 4V4ZM7 9h10M7 13h6" /></>);
export const Send = icon("send", <path d="m2 10 20-8-8 20-3-9-9-3Zm9 3L22 2" />);
export const PanelLeftClose = icon("collapse-sidebar", <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18m7-13-4 4 4 4" /></>);
export const PanelLeftOpen = icon("expand-sidebar", <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18m4-13 4 4-4 4" /></>);
export const Sun = icon("light-theme", <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1" /></>);
export const Moon = icon("dark-theme", <path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z" />);

// Goal identities retain their stored keys, but all built-in options share the same drawing style.
export const Sparkles = icon("wish", <path d="M6 3h12v18l-6-4-6 4V3Z" />);
export const Laptop = icon("laptop", <><path d="M5 4h14v12H5zM2 20h20l-3-4H5l-3 4Z" /></>);
export const Smartphone = icon("mobile-wallet", <><rect x="6" y="2" width="12" height="20" rx="2" /><path d="M10 5h4M11 19h2" /></>);
export const Plane = icon("travel", <path d="m3 9 7 2 7-7c3-3 5-1 2 2l-7 7 2 7-2 2-4-6-4-2 1-2-4-1 2-2Z" />);
export const Car = icon("vehicle", <><path d="m4 10 2-6h12l2 6v9H4v-9Zm0 0h16M7 14h2M15 14h2M6 19v3M18 19v3" /></>);
export const Home = icon("home", <path d="m2 11 10-8 10 8M5 9v12h14V9M10 21v-7h4v7" />);
export const GraduationCap = icon("education", <><path d="m2 8 10-5 10 5-10 5L2 8Zm4 2v7c4 3 8 3 12 0v-7M22 8v9" /></>);
export const Heart = icon("family", <path d="M12 21 3 12C-3 5 7-1 12 7c5-8 15-2 9 5l-9 9Z" />);
export const Dumbbell = icon("fitness", <path d="M3 8v8m3-11v14M6 12h12M18 5v14m3-11v8" />);

export const Utensils = icon("food", <path d="M4 3v6c0 3 6 3 6 0V3M7 3v18M17 21V3c-4 2-4 10 0 10h3V3" />);
export const ShoppingBag = icon("shopping", <><path d="M4 8h16l1 13H3L4 8ZM8 8V6a4 4 0 0 1 8 0v2" /></>);
export const Droplet = icon("water", <path d="M12 2c-2 4-8 9-8 13a8 7 0 0 0 16 0c0-4-6-9-8-13Z" />);
export const Parking = icon("parking", <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 17V7h4a3 3 0 0 1 0 6H9" /></>);
export const Bolt = icon("utilities", <path d="M14 2 4 14h7l-1 8 10-12h-7l1-8Z" />);
export const Wifi = icon("internet", <path d="M2 7a16 16 0 0 1 20 0M6 11a10 10 0 0 1 12 0M10 15a4 4 0 0 1 4 0M12 19v.1" />);
export const MedicalCross = icon("health", <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6V3Z" />);
export const Gift = icon("gift", <><path d="M3 10h18v11H3zM2 6h20v4H2zM12 6v15" /><path d="M12 6C4 7 3 1 7 2c3 0 5 4 5 4Zm0 0c8 1 9-5 5-4-3 0-5 4-5 4Z" /></>);
export const Banknote = icon("income", <><rect x="2" y="5" width="20" height="14" rx="1.5" /><circle cx="12" cy="12" r="3" /><path d="M5 9h1M18 15h1" /></>);
