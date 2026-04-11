/**
 * Кэш истории QA-запросов.
 * Ключ: feedIds (sorted) — привязан к конкретной ленте/папке.
 * Каждая запись хранит вопрос, ответ, источники и метаданные.
 */

export interface QASource {
  link: string;
  title: string;
  feed_name: string;
  published_at: string | null;
  snippet: string;
  article_id: number;
}

export interface QAHistoryItem {
  question: string;
  answer: string;
  sources: QASource[];
  articleCount: number;
  askedAt: string; // ISO
}

const cache = new Map<string, QAHistoryItem[]>();

export function qaCacheKey(feedIds: number[]): string {
  return [...feedIds].sort((a, b) => a - b).join(",");
}

export const qaCache = {
  getHistory: (key: string): QAHistoryItem[] => cache.get(key) ?? [],
  push: (key: string, item: QAHistoryItem): void => {
    const existing = cache.get(key) ?? [];
    // Дедупликация по вопросу — обновляем если уже есть
    const idx = existing.findIndex((h) => h.question === item.question);
    if (idx !== -1) {
      existing[idx] = item;
    } else {
      existing.unshift(item); // новые сверху
    }
    cache.set(key, existing);
  },
  has: (key: string): boolean => cache.has(key),
  clear: (key: string): void => { cache.delete(key); },
};
