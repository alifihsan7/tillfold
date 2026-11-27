"use client";

import { useEffect } from "react";
import { authFetch, getAuthToken } from "@/lib/api";
import { hasTelegramLaunch } from "@/lib/telegramLaunch";
import styles from "./landing.module.css";

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

export function LandingEntry() {
  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), sessionTimeout);
    const openDashboard = (telegram: boolean) => {
      const { search, hash } = window.location;
      window.location.replace(`/dashboard${search}${telegram || hash.startsWith("#/") ? hash : ""}`);
    };

    const routeSession = async () => {
      let redirecting = false;
      try {
        if (hasTelegramLaunch()) {
          openDashboard(true);
          redirecting = true;
          return;
        }
        const token = getAuthToken();
        if (!token) return;

        const response = await authFetch("/api/v1/auth/me", { cache: "no-store", signal: controller.signal });
        if (response.ok && !controller.signal.aborted && getAuthToken() === token) {
          openDashboard(false);
          redirecting = true;
        }
      } catch {
        // Keep the public page available when the session service is unreachable.
      } finally {
        window.clearTimeout(timeout);
        if (!redirecting) document.documentElement.removeAttribute(sessionCheck);
      }
    };

    void routeSession();
    return () => { controller.abort(); window.clearTimeout(timeout); };
  }, []);

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: checkBeforePaint }} />
      <div className={styles.sessionCheck} role="status">Memeriksa sesi…</div>
    </>
  );
}
