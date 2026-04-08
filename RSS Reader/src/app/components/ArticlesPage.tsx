import { useState, useEffect } from "react";
import { Link } from "react-router";
import { Clock, CheckCircle2, Circle, CheckCheck } from "lucide-react";
import { RSSArticle } from "../types";
import { getArticles, toggleArticleRead, markAllAsRead } from "../lib/storage";
import { formatDistanceToNow } from "date-fns";

export function ArticlesPage() {
  const [articles, setArticles] = useState<RSSArticle[]>([]);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const loadArticles = () => {
    const allArticles = getArticles();
    // Sort by date, newest first
    allArticles.sort((a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime());
    setArticles(allArticles);
  };

  useEffect(() => {
    loadArticles();
  }, []);

  const filteredArticles = filter === "unread" 
    ? articles.filter((a) => !a.read) 
    : articles;

  const unreadCount = articles.filter((a) => !a.read).length;

  const handleToggleRead = (articleId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleRead(articleId);
    loadArticles();
  };

  const handleMarkAllAsRead = () => {
    markAllAsRead();
    loadArticles();
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">Статьи</h2>
          <p className="text-sm text-gray-600 mt-1">
            {unreadCount} {unreadCount === 1 ? "непрочитанная статья" : unreadCount > 1 && unreadCount < 5 ? "непрочитанные статьи" : "непрочитанных статей"}
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllAsRead}
              className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              <CheckCheck className="w-4 h-4" />
              Отметить все как прочитанные
            </button>
          )}
          
          <div className="flex gap-1 bg-gray-100 rounded-md p-1">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                filter === "all"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              Все
            </button>
            <button
              onClick={() => setFilter("unread")}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                filter === "unread"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              Непрочитанные
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {filteredArticles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <p className="text-gray-500">
              {filter === "unread" 
                ? "Нет непрочитанных статей. Вы всё прочитали!" 
                : "Статей пока нет. Добавьте источники для начала!"}
            </p>
          </div>
        ) : (
          filteredArticles.map((article) => (
            <Link
              key={article.id}
              to={`/article/${article.id}`}
              className="block bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-blue-200 transition-all"
            >
              <div className="flex items-start gap-4">
                <button
                  onClick={(e) => handleToggleRead(article.id, e)}
                  className="mt-1 flex-shrink-0"
                  aria-label={article.read ? "Mark as unread" : "Mark as read"}
                >
                  {article.read ? (
                    <CheckCircle2 className="w-5 h-5 text-green-600" />
                  ) : (
                    <Circle className="w-5 h-5 text-gray-300 hover:text-gray-400" />
                  )}
                </button>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded">
                      {article.feedTitle}
                    </span>
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(article.pubDate), { addSuffix: true })}
                    </span>
                  </div>

                  <h3 className={`text-lg font-medium mb-2 ${article.read ? "text-gray-600" : "text-gray-900"}`}>
                    {article.title}
                  </h3>

                  <p className="text-sm text-gray-600 line-clamp-2">
                    {article.description}
                  </p>

                  {article.author && (
                    <p className="text-xs text-gray-500 mt-2">Автор: {article.author}</p>
                  )}
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}