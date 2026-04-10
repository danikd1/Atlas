import { useState, useEffect } from "react";
import { useParams, Link, useLocation } from "react-router";
import { Rss, CheckCheck, Loader2, ChevronDown } from "lucide-react";
import { api, ApiFeed, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";

const PAGE_SIZE = 30;

export function FeedArticlesPage() {
  const { feedId } = useParams<{ feedId: string }>();
  const location = useLocation();
  const [feed, setFeed] = useState<ApiFeed | null>(null);
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!feedId) return;
    loadFeed();
  }, [feedId]);

  useEffect(() => {
    if (!feedId) return;
    resetAndLoad();
  }, [feedId, unreadOnly, location.key]);

  const loadFeed = async () => {
    try {
      const f = await api.getFeed(parseInt(feedId!));
      setFeed(f);
    } catch {
      setNotFound(true);
    }
  };

  const resetAndLoad = async () => {
    setIsLoading(true);
    setArticles([]);
    setPage(1);
    try {
      const data = await api.getFeedArticles(parseInt(feedId!), 1, unreadOnly);
      setArticles(data);
      setHasMore(data.length === PAGE_SIZE);
    } catch (e) {
      console.error("Ошибка загрузки статей:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMore = async () => {
    if (isLoadingMore) return;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const data = await api.getFeedArticles(parseInt(feedId!), nextPage, unreadOnly);
      setArticles((prev) => [...prev, ...data]);
      setPage(nextPage);
      setHasMore(data.length === PAGE_SIZE);
    } catch (e) {
      console.error("Ошибка загрузки следующей страницы:", e);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const markAllRead = async () => {
    if (isMarkingAll) return;
    setIsMarkingAll(true);
    try {
      await api.markFeedAllRead(parseInt(feedId!));
      setArticles((prev) => prev.map((a) => ({ ...a, is_read: true })));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
    } catch (e) {
      console.error("Ошибка пометки прочитанными:", e);
    } finally {
      setIsMarkingAll(false);
    }
  };

  const handleReadChange = (id: number, isRead: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_read: isRead } : a));
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_saved: saved } : a));
  };

  const handleArticleClick = async (article: ApiArticleItem) => {
    if (!article.is_read) {
      setArticles((prev) =>
        prev.map((a) => (a.id === article.id ? { ...a, is_read: true } : a))
      );
      try {
        await api.markArticleRead(article.link);
      } catch (e) {
        console.error("Ошибка пометки прочитанной:", e);
      }
    }
  };

  if (notFound) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <Rss className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-500 text-lg">Лента не найдена</p>
        <Link to="/" className="mt-4 inline-block text-sm text-blue-600 hover:underline">
          На главную
        </Link>
      </div>
    );
  }

  const unreadCount = articles.filter((a) => !a.is_read).length;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Заголовок ленты */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          {feed?.favicon_url ? (
            <img
              src={feed.favicon_url}
              alt=""
              className="w-8 h-8 rounded-md flex-shrink-0"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <div className="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center flex-shrink-0">
              <Rss className="w-4 h-4 text-blue-600" />
            </div>
          )}
          <h1 className="text-2xl font-bold text-gray-900">
            {feed?.name ?? "Загрузка..."}
          </h1>
        </div>
        {feed?.description && (
          <p className="text-sm text-gray-500 mb-1">{feed.description}</p>
        )}
      </div>

      {/* Панель управления */}
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">Только непрочитанные</span>
          </label>
        </div>
        <button
          onClick={markAllRead}
          disabled={isMarkingAll || unreadCount === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {isMarkingAll ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <CheckCheck className="w-3.5 h-3.5" />
          )}
          Пометить все прочитанными
        </button>
      </div>

      {/* Список статей */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          Загрузка статей...
        </div>
      ) : articles.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <Rss className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">
            {unreadOnly ? "Нет непрочитанных статей" : "Статей от этого источника пока нет"}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {articles.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              variant="row"
              onClick={handleArticleClick}
              onReadChange={handleReadChange}
              onSavedChange={handleSavedChange}
            />
          ))}

          {/* Загрузить ещё */}
          {hasMore && (
            <div className="pt-2 flex justify-center">
              <button
                onClick={loadMore}
                disabled={isLoadingMore}
                className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 transition-colors"
              >
                {isLoadingMore ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
                Загрузить ещё
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
