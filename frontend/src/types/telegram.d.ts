export interface TelegramWebAppData {
  initData: string;
  initDataUnsafe?: {
    query_id?: string;
    user?: {
      id: number;
      first_name?: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    auth_date?: string;
    hash?: string;
  };
  ready: () => void;
  expand: () => void;
  close: () => void;
  openLink?: (url: string) => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  isExpanded?: boolean;
  viewportHeight?: number;
  viewportStableHeight?: number;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebAppData;
    };
  }
}
