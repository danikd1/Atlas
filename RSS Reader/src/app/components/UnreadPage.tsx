import { useState, useEffect, useCallback } from "react";
import { BookOpen } from "lucide-react";
import { api, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";

export function UnreadPage() {
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const loadArticles = useCallback(async (pageNum: number, append: boolean) => {
    try {
      const data = await api.getUnreadArticles(pageNum);
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
    if (isRead) {
      setArticles((prev) => prev.filter((a) => a.id !== id));
    } else {
      setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_read: false } : a));
    }
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_saved: saved } : a));
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <BookOpen className="w-6 h-6 text-green-600" />
          <h1 className="text-3xl font-bold text-gray-900">Непрочитанное</h1>
        </div>
        <p className="text-gray-600">
          {articles.length} {articles.length === 1 ? "непрочитанная статья" : articles.length < 5 ? "непрочитанные статьи" : "непрочитанных статей"}
        </p>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center text-gray-400">
            Загрузка...
          </div>
        ) : articles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">Все статьи прочитаны! 🎉</p>
          </div>
        ) : (
          <>
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                variant="card"
                onReadChange={handleReadChange}
                onSavedChange={handleSavedChange}
              />
            ))}
            {hasMore && (
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
