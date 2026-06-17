import type { TranslationResult } from "../components/TranslateButton";

/**
 * Модуль-уровневый кэш переводов.
 * ArticleCard (сайдбар) пишет после перевода,
 * ArticleDetailPage читает при открытии статьи.
 */
const cache = new Map<number, TranslationResult>();

export const translationCache = {
  get: (articleId: number): TranslationResult | null => cache.get(articleId) ?? null,
  set: (articleId: number, result: TranslationResult) => cache.set(articleId, result),
  has: (articleId: number): boolean => cache.has(articleId),
};
