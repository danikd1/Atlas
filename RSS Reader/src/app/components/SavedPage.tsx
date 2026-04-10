import { useState, useEffect } from "react";
import { Bookmark } from "lucide-react";
import { api, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";

export function SavedPage() {
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  useEffect(() => {
    loadArticles(1, false);
  }, []);

  const loadArticles = async (pageNum: number, append: boolean) => {
    if (pageNum === 1) setIsLoading(true);
    try {
      const data = await api.getBookmarks(pageNum);
      if (append) {
        setArticles((prev) => [...prev, ...data]);
      } else {
        setArticles(data);
      }
      setHasMore(data.length === 30);
    } catch (e) {
      console.error("Ошибка загрузки закладок:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadMore = async () => {
    const nextPage = page + 1;
    setIsLoadingMore(true);
    await loadArticles(nextPage, true);
    setPage(nextPage);
    setIsLoadingMore(false);
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    if (!saved) {
      // Убрали из закладок — удаляем из списка
      setArticles((prev) => prev.filter((a) => a.id !== id));
    } else {
      setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_saved: true } : a));
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Bookmark className="w-6 h-6 text-yellow-600" />
          <h1 className="text-3xl font-bold text-gray-900">Сохраненное</h1>
        </div>
        <p className="text-gray-600">
          {articles.length} {articles.length === 1 ? "сохраненная статья" : articles.length < 5 ? "сохраненные статьи" : "сохраненных статей"}
        </p>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center text-gray-400">
            Загрузка...
          </div>
        ) : articles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <Bookmark className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">У вас пока нет сохраненных статей</p>
            <p className="text-sm text-gray-400 mt-2">
              Нажмите на звезду рядом со статьёй, чтобы сохранить её
            </p>
          </div>
        ) : (
          <>
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                variant="card"
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
