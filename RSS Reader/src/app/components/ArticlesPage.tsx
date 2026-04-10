import { useState, useEffect, useCallback } from "react";
import { api, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";

export function ArticlesPage() {
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const loadArticles = useCallback(async (pageNum: number, append: boolean) => {
    try {
      const data = await api.getAllArticles(pageNum);
      if (append) {
        setArticles((prev) => [...prev, ...data]);
      } else {
        setArticles(data);
      }
      setHasMore(data.length === 30);
    } catch (e) {
      console.error("Ошибка загрузки статей:", e);
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setPage(1);
    loadArticles(1, false).finally(() => setIsLoading(false));
  }, [loadArticles]);

  const handleLoadMore = async () => {
    const nextPage = page + 1;
    setIsLoadingMore(true);
    await loadArticles(nextPage, true);
    setPage(nextPage);
    setIsLoadingMore(false);
  };

  const handleReadChange = (id: number, isRead: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_read: isRead } : a));
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_saved: saved } : a));
  };

  const filteredArticles = filter === "unread"
    ? articles.filter((a) => !a.is_read)
    : articles;

  const unreadCount = articles.filter((a) => !a.is_read).length;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">Статьи</h2>
          <p className="text-sm text-gray-600 mt-1">
            {unreadCount} {unreadCount === 1 ? "непрочитанная" : unreadCount < 5 ? "непрочитанные" : "непрочитанных"}
          </p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-md p-1">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1 text-sm rounded transition-colors ${
              filter === "all" ? "bg-white text-gray-900 shadow-sm" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Все
          </button>
          <button
            onClick={() => setFilter("unread")}
            className={`px-3 py-1 text-sm rounded transition-colors ${
              filter === "unread" ? "bg-white text-gray-900 shadow-sm" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Непрочитанные
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center text-gray-400">
            Загрузка...
          </div>
        ) : filteredArticles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <p className="text-gray-500">
              {filter === "unread" ? "Нет непрочитанных статей." : "Статей пока нет. Добавьте источники!"}
            </p>
          </div>
        ) : (
          <>
            {filteredArticles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                variant="card"
                onReadChange={handleReadChange}
                onSavedChange={handleSavedChange}
              />
            ))}
            {hasMore && filter === "all" && (
              <button
                onClick={handleLoadMore}
                disabled={isLoadingMore}
                className="w-full py-3 text-sm text-blue-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-60"
              >
                {isLoadingMore ? "Загрузка..." : "Загрузить ещё"}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
