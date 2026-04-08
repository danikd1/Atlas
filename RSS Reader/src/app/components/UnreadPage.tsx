import { useState, useEffect } from "react";
import { Link } from "react-router";
import { BookOpen, Bookmark, Clock } from "lucide-react";
import { getArticles, toggleArticleSaved, toggleArticleRead } from "../lib/storage";
import { RSSArticle } from "../types";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

export function UnreadPage() {
  const [articles, setArticles] = useState<RSSArticle[]>([]);

  useEffect(() => {
    loadArticles();
  }, []);

  const loadArticles = () => {
    const allArticles = getArticles();
    const unreadArticles = allArticles.filter((article) => !article.read);

    // Sort by date, newest first
    unreadArticles.sort((a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime());
    setArticles(unreadArticles);
  };

  const handleToggleSaved = (e: React.MouseEvent, articleId: string) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleSaved(articleId);
    loadArticles();
  };

  const handleToggleRead = (e: React.MouseEvent, articleId: string) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleRead(articleId);
    loadArticles();
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
        {articles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">Все статьи прочитаны! 🎉</p>
          </div>
        ) : (
          articles.map((article) => (
            <Link
              key={article.id}
              to={`/article/${article.id}`}
              className="block bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:shadow-md hover:border-blue-200 transition-all"
            >
              <div className="flex items-start justify-between gap-4 mb-2">
                <h3 className="text-lg font-medium text-gray-900 flex-1">
                  {article.title}
                </h3>
                <button
                  onClick={(e) => handleToggleSaved(e, article.id)}
                  className={`flex-shrink-0 p-1 rounded transition-colors ${
                    article.saved ? "text-yellow-500" : "text-gray-400 hover:text-yellow-500"
                  }`}
                >
                  <Bookmark className={`w-5 h-5 ${article.saved ? "fill-current" : ""}`} />
                </button>
              </div>

              <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                {article.description}
              </p>

              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-blue-600">{article.feedTitle}</span>
                  <span className="flex items-center gap-1 text-gray-500">
                    <Clock className="w-3 h-3" />
                    {formatDistanceToNow(new Date(article.pubDate), { 
                      addSuffix: true,
                      locale: ru 
                    })}
                  </span>
                </div>

                <button
                  onClick={(e) => handleToggleRead(e, article.id)}
                  className="px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700 hover:bg-green-200 transition-colors"
                >
                  Отметить прочитанным
                </button>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
