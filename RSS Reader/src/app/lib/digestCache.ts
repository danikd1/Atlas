/**
 * Модульный кэш дайджестов.
 * Ключ: feedIds (sorted) + period ("day" | "week" | "month")
 * Точные даты хранятся внутри CachedDigest, но не участвуют в ключе.
 */

export interface CachedDigest {
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
}

const cache = new Map<string, CachedDigest>();

export function digestCacheKey(feedIds: number[], period: string): string {
  return `${[...feedIds].sort((a, b) => a - b).join(",")}_${period}`;
}

export const digestCache = {
  get: (key: string): CachedDigest | null => cache.get(key) ?? null,
  set: (key: string, result: CachedDigest): void => { cache.set(key, result); },
  has: (key: string): boolean => cache.has(key),
  clear: (): void => { cache.clear(); },
};
