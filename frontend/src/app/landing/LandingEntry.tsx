"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, type ReactNode } from "react";
import { authFetch, getAuthToken } from "@/lib/api";
import { hasTelegramLaunch } from "@/lib/telegramLaunch";
import styles from "./landing.module.css";

const FinanceDashboard = dynamic(() => import("../dashboard/FinanceDashboard"), {
  ssr: false,
  loading: () => <div className={styles.sessionStatus} role="status">Memuat dashboard…</div>,
});

const sessionCheck = "data-tillfold-session-check";
const sessionTimeout = 5_000;

// The exported landing page is public. Hide it briefly while an existing session is checked.
const checkBeforePaint = `
  try {
    if (localStorage.getItem("ai7_token") || new URLSearchParams(location.hash.slice(1)).has("tgWebAppData")) {
      document.documentElement.setAttribute("${sessionCheck}", "");
      setTimeout(() => document.documentElement.removeAttribute("${sessionCheck}"), ${sessionTimeout});
    }
  } catch {}
`;

export function LandingEntry({ children }: { children: ReactNode }) {
  const [showDashboard, setShowDashboard] = useState(false);

  useEffect(() => {
    if (showDashboard) document.documentElement.removeAttribute(sessionCheck);
  }, [showDashboard]);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), sessionTimeout);
    const routeSession = async () => {
      let openingDashboard = false;
      try {
        if (hasTelegramLaunch()) {
          setShowDashboard(true);
          openingDashboard = true;
          return;
        }
        const token = getAuthToken();
        if (!token) return;

        const response = await authFetch("/api/v1/auth/me", { cache: "no-store", signal: controller.signal });
        if (response.ok && !controller.signal.aborted && getAuthToken() === token) {
          setShowDashboard(true);
          openingDashboard = true;
        }
      } catch {
        // Keep the public page available when the session service is unreachable.
      } finally {
        window.clearTimeout(timeout);
        if (!openingDashboard) document.documentElement.removeAttribute(sessionCheck);
      }
    };

    void routeSession();
    return () => { controller.abort(); window.clearTimeout(timeout); };
  }, []);

  if (showDashboard) {
    return <FinanceDashboard onLogout={() => {
      const { pathname, search } = window.location;
      window.history.replaceState(window.history.state, "", pathname + search);
      setShowDashboard(false);
    }} />;
  }

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: checkBeforePaint }} />
      <div className={`${styles.sessionStatus} ${styles.sessionCheck}`} role="status">Memeriksa sesi…</div>
      {children}
    </>
  );
}
