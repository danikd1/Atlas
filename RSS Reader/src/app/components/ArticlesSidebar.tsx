import { useState, useEffect } from "react";
import { X, Rss, Loader2 } from "lucide-react";
import { RSSFeed } from "../types";
import { api, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";

interface ArticlesSidebarProps {
  feed: RSSFeed;
  onClose: () => void;
}

export function ArticlesSidebar({ feed, onClose }: ArticlesSidebarProps) {
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadArticles();
  }, [feed.id]);

  const loadArticles = async () => {
    setIsLoading(true);
    try {
      const ids = feed.feedIds && feed.feedIds.length > 0 ? feed.feedIds : [parseInt(feed.id)];
      const data = ids.length > 1
        ? await api.getArticlesByFeedIds(ids)
        : await api.getFeedArticles(ids[0], 1, false);
      setArticles(data);
    } catch (e) {
      console.error("Ошибка загрузки статей:", e);
      setArticles([]);
    } finally {
      setIsLoading(false);
    }
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

  const handleReadChange = (id: number, isRead: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_read: isRead } : a));
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    setArticles((prev) => prev.map((a) => a.id === id ? { ...a, is_saved: saved } : a));
  };

  const unreadCount = articles.filter((a) => !a.is_read).length;
  const isMultiFeed = feed.feedIds && feed.feedIds.length > 1;

  return (
    <aside className="w-full bg-white border-l border-gray-200 h-full overflow-y-auto flex-shrink-0 flex flex-col">
      {/* Заголовок */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 z-10 flex-shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {feed.favicon_url ? (
              <img
                src={feed.favicon_url}
                alt=""
                className="w-5 h-5 rounded flex-shrink-0"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            ) : (
              <Rss className="w-4 h-4 text-gray-400 flex-shrink-0" />
            )}
            <h2 className="font-semibold text-gray-900 text-sm truncate">{feed.title}</h2>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        {!isLoading && articles.length > 0 && (
          <p className="text-xs text-gray-400 mt-1">
            {unreadCount > 0 ? `${unreadCount} непрочитанных · ` : ""}{articles.length} статей
          </p>
        )}
      </div>

      {/* Список статей */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            <span className="text-sm">Загрузка...</span>
          </div>
        ) : articles.length === 0 ? (
          <div className="text-center py-12 px-4">
            <Rss className="w-8 h-8 text-gray-200 mx-auto mb-2" />
            <p className="text-sm text-gray-400">Статей пока нет</p>
          </div>
        ) : (
          articles.map((article) => (
            <ArticleCard
              key={article.id}
              article={article}
              variant="sidebar"
              onClick={handleArticleClick}
              onReadChange={handleReadChange}
              onSavedChange={handleSavedChange}
              showSource={isMultiFeed}
            />
          ))
        )}
      </div>
    </aside>
  );
}
