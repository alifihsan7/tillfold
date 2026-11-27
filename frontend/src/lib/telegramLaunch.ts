import type { TelegramWebAppData } from "@/types/telegram";

export function hasTelegramLaunch() {
  return Boolean(
    window.Telegram?.WebApp?.initData ||
    new URLSearchParams(window.location.hash.slice(1)).get("tgWebAppData"),
  );
}

export async function getTelegramWebApp(): Promise<TelegramWebAppData | undefined> {
  if (window.Telegram?.WebApp || !hasTelegramLaunch()) return window.Telegram?.WebApp;

  const script = document.querySelector('script[src="https://telegram.org/js/telegram-web-app.js"]');
  if (script) {
    await new Promise<void>((resolve) => {
      const finish = () => {
        window.clearTimeout(timeout);
        script.removeEventListener("load", finish);
        script.removeEventListener("error", finish);
        resolve();
      };
      const timeout = window.setTimeout(finish, 3000);
      script.addEventListener("load", finish);
      script.addEventListener("error", finish);
    });
  }
  return window.Telegram?.WebApp;
}
