import { useState, useEffect } from "react";
import { Calendar } from "lucide-react";
import { api, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";

const formatHHMM = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
};

export function TodayPage() {
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadArticles();
  }, []);

  const loadArticles = async () => {
    setIsLoading(true);
    try {
      const data = await api.getTodayArticles();
      setArticles(data);
    } catch (e) {
      console.error("Ошибка загрузки статей:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReadChange = (id: number, isRead: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_read: isRead } : a));
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_saved: saved } : a));
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Calendar className="w-6 h-6 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">Сегодня</h1>
        </div>
        <p className="text-gray-600">
          {articles.length} {articles.length === 1 ? "статья" : articles.length < 5 ? "статьи" : "статей"} опубликовано сегодня
        </p>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center text-gray-400">
            Загрузка...
          </div>
        ) : articles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">Сегодня статей нет</p>
          </div>
        ) : (
          articles.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              variant="card"
              formatTime={formatHHMM}
              onReadChange={handleReadChange}
              onSavedChange={handleSavedChange}
            />
          ))
        )}
      </div>
    </div>
  );
}
