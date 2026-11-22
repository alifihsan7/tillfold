"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type ThemeMode = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

interface ThemeContextType {
  theme: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = "ai7-finance-theme";

/** Fold 2 canvas colors (--fold-canvas) for browser and Telegram chrome. */
export const CHROME_COLOR: Record<"dark" | "light", string> = { dark: "#171a1f", light: "#e4e7eb" };

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>("dark");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("dark");
  const [mounted, setMounted] = useState(false);

  // Initialize theme from localStorage or OS preference
  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
      if (saved && (saved === "dark" || saved === "light" || saved === "system")) {
        setThemeState(saved);
      } else {
        // Default to dark for AI7 Finance obsidian slate heritage
        setThemeState("dark");
      }
    } catch {
      setThemeState("dark");
    }
  }, []);

  // Compute resolved theme & apply to DOM
  useEffect(() => {
    if (!mounted) return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const resolveCurrentTheme = (currentMode: ThemeMode): ResolvedTheme => {
      if (currentMode === "system") {
        return mediaQuery.matches ? "dark" : "light";
      }
      return currentMode;
    };

    const effectiveTheme = resolveCurrentTheme(theme);
    setResolvedTheme(effectiveTheme);

    const root = document.documentElement;
    if (effectiveTheme === "light") {
      root.classList.add("light");
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
      root.style.colorScheme = "light";
    } else {
      root.classList.remove("light");
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
      root.style.colorScheme = "dark";
    }

    // Sync theme-color meta tag for mobile browser chrome
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.setAttribute("content", CHROME_COLOR[effectiveTheme]);
    }

    // Sync Telegram WebApp colors if running inside Telegram Mini App
    if (typeof window !== "undefined" && (window as unknown as { Telegram?: { WebApp?: { setHeaderColor?: (c: string) => void; setBackgroundColor?: (c: string) => void } } }).Telegram?.WebApp) {
      const tg = (window as unknown as { Telegram: { WebApp: { setHeaderColor?: (c: string) => void; setBackgroundColor?: (c: string) => void } } }).Telegram.WebApp;
      try {
        if (typeof tg.setHeaderColor === "function") {
          tg.setHeaderColor(CHROME_COLOR[effectiveTheme]);
        }
        if (typeof tg.setBackgroundColor === "function") {
          tg.setBackgroundColor(CHROME_COLOR[effectiveTheme]);
        }
      } catch {
        // Non-fatal if Telegram WebApp JS bridge isn't fully ready
      }
    }

    // Listener for system preference changes
    const handleChange = () => {
      if (theme === "system") {
        const newEffective = mediaQuery.matches ? "dark" : "light";
        setResolvedTheme(newEffective);
        if (newEffective === "light") {
          root.classList.add("light");
          root.classList.remove("dark");
          root.setAttribute("data-theme", "light");
          root.style.colorScheme = "light";
        } else {
          root.classList.remove("light");
          root.classList.add("dark");
          root.setAttribute("data-theme", "dark");
          root.style.colorScheme = "dark";
        }
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme, mounted]);

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem(STORAGE_KEY, newTheme);
    } catch {
      // Storage might be restricted
    }
  };

  const toggleTheme = () => {
    // If currently dark (or resolved dark), toggle to light. Otherwise toggle to dark.
    const nextTheme: ThemeMode = resolvedTheme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        resolvedTheme,
        setTheme,
        toggleTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
