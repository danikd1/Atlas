import type { RSSFeed } from "../types";

const API_BASE = "http://localhost:8000";

// ─── API response types ────────────────────────────────────────────────────

export interface ApiFeed {
  id: number;
  url: string;
  name: string;
  favicon_url: string | null;
  description: string | null;
  enabled: boolean;
  error_count: number;
  last_fetched_at: string | null;
  last_error: string | null;
  folder_id: number | null;
  hidden: boolean;
  unread_count: number;
  created_at: string | null;
}

export interface ApiCatalogFeed {
  id: number;
  url: string;
  name: string;
  favicon_url: string | null;
  description: string | null;
  category: string | null;
  enabled: boolean;
  error_count: number;
  last_fetched_at: string | null;
  subscribers: number;
  posts_per_week: number;
  last_post_at: string | null;
  is_subscribed: boolean;
  source_description: string | null;
}

export interface ApiFolder {
  id: number;
  name: string;
  position: number;
}

export interface FeedValidateResponse {
  valid: boolean;
  name: string | null;
  description: string | null;
  favicon_url: string | null;
  suggested_category: string | null;
  error: string | null;
}

// ─── Mapper: ApiFeed → RSSFeed ─────────────────────────────────────────────

export function apiFeedToRSSFeed(f: ApiFeed): RSSFeed {
  return {
    id: f.id.toString(),
    title: f.name,
    url: f.url,
    description: f.description ?? undefined,
    addedAt: f.created_at ?? undefined,
    folderId: f.folder_id?.toString(),
    hidden: f.hidden,
    unread_count: f.unread_count,
    favicon_url: f.favicon_url ?? undefined,
    error_count: f.error_count,
    last_error: f.last_error ?? undefined,
    category: f.category ?? undefined,
  };
}

// ─── API client ────────────────────────────────────────────────────────────

export const api = {
  async getFeeds(includeHidden = false): Promise<ApiFeed[]> {
    const res = await fetch(`${API_BASE}/api/feeds?include_hidden=${includeHidden}`);
    if (!res.ok) throw new Error("Не удалось загрузить ленты");
    return res.json();
  },

  async validateFeed(url: string): Promise<FeedValidateResponse> {
    const res = await fetch(`${API_BASE}/api/feeds/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error("Ошибка при проверке ленты");
    return res.json();
  },

  async addFeed(data: {
    url: string;
    name: string;
    favicon_url?: string | null;
    description?: string | null;
    category?: string | null;
    folder_id?: number | null;
  }): Promise<ApiFeed> {
    const res = await fetch(`${API_BASE}/api/feeds`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Не удалось добавить ленту");
    return res.json();
  },

  async deleteFeed(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/api/feeds/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 404) throw new Error("Не удалось удалить ленту");
  },

  async patchFeed(id: number, data: {
    name?: string;
    enabled?: boolean;
    folder_id?: number | null;
    hidden?: boolean;
  }): Promise<ApiFeed> {
    const res = await fetch(`${API_BASE}/api/feeds/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Не удалось обновить ленту");
    return res.json();
  },

  async getCatalog(): Promise<ApiCatalogFeed[]> {
    const res = await fetch(`${API_BASE}/api/catalog`);
    if (!res.ok) throw new Error("Не удалось загрузить каталог");
    return res.json();
  },

  async createFolder(name: string): Promise<ApiFolder> {
    const res = await fetch(`${API_BASE}/api/folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error("Не удалось создать папку");
    return res.json();
  },

  async deleteFolder(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/api/folders/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 404) throw new Error("Не удалось удалить папку");
  },
};
