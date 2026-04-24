import type { RSSFeed } from "../types";
import { authService } from "./authService";

const API_BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

// ─── API response types ────────────────────────────────────────────────────

export interface ApiFeed {
  id: number;
  url: string;
  name: string;
  favicon_url: string | null;
  description: string | null;
  category: string | null;
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
  favicon_url: string | null;
}

export interface ApiArticleItem {
  id: number;
  link: string;
  title: string | null;
  summary: string | null;
  published_at: string | null;
  source: string | null;
  feed_id: number | null;
  is_read: boolean;
  is_saved: boolean;
}

export interface ApiArticleDetail {
  id: number;
  link: string;
  title: string | null;
  summary: string | null;
  full_text: string | null;
  published_at: string | null;
  source: string | null;
  is_read: boolean;
  is_saved: boolean;
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

// ─── Auth helpers ─────────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = authService.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function handleUnauthorized(res: Response): void {
  if (res.status === 401) {
    authService.logout();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
}

// ─── GigaChat helpers ─────────────────────────────────────────────────────────

function gigachatParams(): { gigachat_credentials?: string; gigachat_model?: string } {
  const credentials = localStorage.getItem("gigachat_credentials");
  const model = localStorage.getItem("gigachat_model");
  return {
    ...(credentials ? { gigachat_credentials: credentials } : {}),
    ...(model ? { gigachat_model: model } : {}),
  };
}

// ─── API client ────────────────────────────────────────────────────────────

export const api = {
  async getFeeds(includeHidden = false): Promise<ApiFeed[]> {
    const res = await fetch(`${API_BASE}/api/feeds?include_hidden=${includeHidden}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить ленты");
    return res.json();
  },

  async getFeed(id: number): Promise<ApiFeed> {
    const res = await fetch(`${API_BASE}/api/feeds/${id}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Лента не найдена");
    return res.json();
  },

  async validateFeed(url: string): Promise<FeedValidateResponse> {
    const res = await fetch(`${API_BASE}/api/feeds/validate`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ url, ...gigachatParams() }),
    });
    handleUnauthorized(res);
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
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось добавить ленту");
    return res.json();
  },

  async addFeedsBatch(feeds: {
    url: string;
    name: string;
    favicon_url?: string | null;
    description?: string | null;
    category?: string | null;
    folder_id?: number | null;
  }[]): Promise<ApiFeed[]> {
    const res = await fetch(`${API_BASE}/api/feeds/batch`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ feeds }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось добавить ленты");
    return res.json();
  },

  async deleteFeed(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/api/feeds/${id}`, { method: "DELETE", headers: authHeaders() });
    handleUnauthorized(res);
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
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось обновить ленту");
    return res.json();
  },

  async getCatalog(): Promise<ApiCatalogFeed[]> {
    const res = await fetch(`${API_BASE}/api/catalog`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить каталог");
    return res.json();
  },

  async getFolders(): Promise<ApiFolder[]> {
    const res = await fetch(`${API_BASE}/api/folders`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить папки");
    return res.json();
  },

  async createFolder(name: string, favicon_url?: string | null): Promise<ApiFolder> {
    const res = await fetch(`${API_BASE}/api/folders`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ name, favicon_url: favicon_url ?? null }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось создать папку");
    return res.json();
  },

  async patchFolder(id: number, data: { name?: string; position?: number }): Promise<ApiFolder> {
    const res = await fetch(`${API_BASE}/api/folders/${id}`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось обновить папку");
    return res.json();
  },

  async deleteFolder(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/api/folders/${id}`, { method: "DELETE", headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok && res.status !== 404) throw new Error("Не удалось удалить папку");
  },

  async getTodayArticles(): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/articles/today`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить статьи за сегодня");
    return res.json();
  },

  async getUnreadArticles(page = 1): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/articles/unread?page=${page}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить непрочитанные статьи");
    return res.json();
  },

  async getAllArticles(page = 1): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/articles?page=${page}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить статьи");
    return res.json();
  },

  async searchArticles(query: string, limit = 20): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/articles/search?q=${encodeURIComponent(query)}&limit=${limit}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка поиска");
    return res.json();
  },

  async markArticleRead(link: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/articles/read`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ link }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось пометить статью прочитанной");
  },

  async translateArticle(id: number): Promise<{ title: string | null; summary: string | null; full_text: string | null }> {
    const res = await fetch(`${API_BASE}/api/articles/${id}/translate`, { method: "POST", headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка перевода статьи");
    return res.json();
  },

  async unmarkArticleRead(link: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/articles/read`, {
      method: "DELETE",
      headers: authHeaders(),
      body: JSON.stringify({ link }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось снять метку прочитанного");
  },

  async getArticlesByFeedIds(feedIds: number[], page = 1): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/articles/by-feeds?feed_ids=${feedIds.join(",")}&page=${page}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить статьи");
    return res.json();
  },

  async getFeedArticles(feedId: number, page = 1, unreadOnly = false): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/feeds/${feedId}/articles?page=${page}&unread_only=${unreadOnly}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить статьи ленты");
    return res.json();
  },

  async markFeedAllRead(feedId: number): Promise<{ marked: number }> {
    const res = await fetch(`${API_BASE}/api/feeds/${feedId}/read-all`, { method: "POST", headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось пометить все статьи прочитанными");
    return res.json();
  },

  async getArticleById(id: number): Promise<ApiArticleDetail> {
    const res = await fetch(`${API_BASE}/api/articles/${id}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить статью");
    return res.json();
  },

  async getRssStatus(): Promise<{
    last_run_at: string | null;
    next_run_at: string | null;
    is_running: boolean;
    last_new_articles: number | null;
    interval_hours: number;
    text_extraction_running: boolean;
    text_extraction_pending: number;
    rag_indexing: boolean;
    rag_paused: boolean;
    rag_indexed: number;
    rag_pending: number;
  }> {
    const res = await fetch(`${API_BASE}/api/rss/status`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось получить статус");
    return res.json();
  },

  async startExtractionWorker(): Promise<void> {
    const res = await fetch(`${API_BASE}/api/rss/extract`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ full_scan: false }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось запустить воркер");
  },

  async startRagIndexer(): Promise<void> {
    const res = await fetch(`${API_BASE}/api/rss/index`, {
      method: "POST",
      headers: authHeaders(),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось запустить индексацию");
  },

  async pauseRagIndexer(): Promise<void> {
    const res = await fetch(`${API_BASE}/api/rss/index/pause`, {
      method: "POST",
      headers: authHeaders(),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось поставить на паузу");
  },

  async resumeRagIndexer(): Promise<void> {
    const res = await fetch(`${API_BASE}/api/rss/index/resume`, {
      method: "POST",
      headers: authHeaders(),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось возобновить");
  },

  async triggerCollect(): Promise<{ new_articles: number }> {
    const res = await fetch(`${API_BASE}/api/rss/collect`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({}),
    });
    handleUnauthorized(res);
    if (res.status === 409) throw new Error("already_running");
    if (!res.ok) throw new Error("Не удалось запустить сбор");
    return res.json();
  },

  async bookmarkArticle(link: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/articles/bookmark`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ link }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось добавить закладку");
  },

  async unbookmarkArticle(link: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/articles/bookmark`, {
      method: "DELETE",
      headers: authHeaders(),
      body: JSON.stringify({ link }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось убрать закладку");
  },

  async getBookmarks(page = 1): Promise<ApiArticleItem[]> {
    const res = await fetch(`${API_BASE}/api/bookmarks?page=${page}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить закладки");
    return res.json();
  },

  async summarizeArticle(id: number): Promise<{ ai_summary: string | null; cached: boolean; error?: string }> {
    const res = await fetch(`${API_BASE}/api/articles/${id}/summarize`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(gigachatParams()),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось получить резюме");
    return res.json();
  },

  async feedQA(params: {
    feed_ids: number[];
    collection_id?: number;
    question: string;
    from_date?: string;
    to_date?: string;
    top_k?: number;
  }): Promise<{
    status: string;
    answer: string | null;
    sources: { link: string; title: string; feed_name: string; published_at: string | null; snippet: string; article_id: number }[];
    article_count: number;
    error?: string;
  }> {
    const res = await fetch(`${API_BASE}/api/feeds/qa`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ...params, ...gigachatParams() }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка QA");
    return res.json();
  },

  async getCollectionArticles(collectionId: number, _page = 1): Promise<ApiArticleItem[]> {
    // Используем BERTopic-эндпоинт: статьи через assignments → processed_articles
    const res = await fetch(`${API_BASE}/api/bertopic/collections/${collectionId}/articles`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось загрузить статьи коллекции");
    const data = await res.json();
    return (Array.isArray(data) ? data : []).map((a: any) => ({
      id: a.id ?? 0,
      link: a.link ?? "",
      title: a.title ?? null,
      summary: a.summary ?? null,
      published_at: a.published_at ?? null,
      source: a.source ?? null,
      feed_id: a.feed_id ?? null,
      is_read: a.is_read ?? false,
      is_saved: a.is_saved ?? false,
    }));
  },

  // ── BERTopic ──────────────────────────────────────────────────────────────

  async bertopicRun(params?: {
    min_topic_size?: number;
    n_categories?: number;
    skip_rag?: boolean;
    source_filter?: string;
    limit?: number;
    days_back?: number;
  }): Promise<{ task_id: string; status: string; message: string }> {
    const res = await fetch(`${API_BASE}/api/bertopic/run`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ...(params ?? {}), ...gigachatParams() }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка запуска BERTopic");
    return res.json();
  },

  async bertopicStatus(taskId: string): Promise<{
    task_id: string;
    status: string;
    progress: number;
    message: string;
    error?: string;
    result?: {
      n_topics: number;
      n_articles: number;
      n_collections: number;
      n_assignments: number;
      model_version: string;
    };
    started_at?: string;
  }> {
    const res = await fetch(`${API_BASE}/api/bertopic/status/${taskId}`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Задача не найдена");
    return res.json();
  },

  async bertopicTopics(): Promise<{
    topics: {
      id: number;
      name: string;
      description?: string;
      keywords?: string;
      bertopic_topic_id?: number;
      article_count: number;
      model_version?: string;
    }[];
    total: number;
  }> {
    const res = await fetch(`${API_BASE}/api/bertopic/topics`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка загрузки тем");
    return res.json();
  },

  async feedDigest(params: {
    feed_ids: number[];
    collection_id?: number;
    from_date?: string;
    to_date?: string;
  }): Promise<{
    title: string;
    feed_ids: number[];
    generated_at: string;
    from_date: string | null;
    to_date: string | null;
    article_count: number;
    sections: Record<string, {
      label: string;
      description: string;
      articles: { link: string; title: string; published_at: string | null; article_id: number }[];
    }[]>;
  }> {
    const res = await fetch(`${API_BASE}/api/feeds/digest`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ ...params, ...gigachatParams() }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка дайджеста");
    return res.json();
  },

  async gigachatTest(credentials: string, model?: string): Promise<{ ok: boolean; error?: string }> {
    const res = await fetch(`${API_BASE}/api/gigachat/test`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ credentials, ...(model ? { model } : {}) }),
    });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Ошибка проверки GigaChat");
    return res.json();
  },

  async login(email: string, password: string): Promise<{ access_token: string }> {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Ошибка входа");
    }
    return res.json();
  },

  async register(email: string, password: string): Promise<{ access_token: string }> {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Ошибка регистрации");
    }
    return res.json();
  },

  async getMe(): Promise<{ id: number; email: string; created_at?: string }> {
    const res = await fetch(`${API_BASE}/api/auth/me`, { headers: authHeaders() });
    handleUnauthorized(res);
    if (!res.ok) throw new Error("Не удалось получить данные пользователя");
    return res.json();
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/auth/change-password`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    handleUnauthorized(res);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail ?? "Не удалось сменить пароль");
    }
  },
};
