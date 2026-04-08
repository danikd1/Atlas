import { useState, useEffect } from "react";
import { useParams, Link } from "react-router";
import { Rss, Bookmark, Clock, ArrowLeft } from "lucide-react";
import { getArticles, getFeeds, toggleArticleSaved, toggleArticleRead } from "../lib/storage";
import { RSSArticle, RSSFeed } from "../types";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

export function FeedArticlesPage() {
  const { feedId } = useParams<{ feedId: string }>();
  const [articles, setArticles] = useState<RSSArticle[]>([]);
  const [feed, setFeed] = useState<RSSFeed | null>(null);

  useEffect(() => {
    loadData();
  }, [feedId]);

  const loadData = () => {
    if (!feedId) return;

    const feeds = getFeeds();
    const currentFeed = feeds.find((f) => f.id === feedId);
    setFeed(currentFeed || null);

    const allArticles = getArticles();
    const feedArticles = allArticles.filter((article) => article.feedId === feedId);

    // Sort by date, newest first
    feedArticles.sort((a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime());
    setArticles(feedArticles);
  };

  const handleToggleSaved = (e: React.MouseEvent, articleId: string) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleSaved(articleId);
    loadData();
  };

  const handleToggleRead = (e: React.MouseEvent, articleId: string) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleRead(articleId);
    loadData();
  };

  if (!feed) {
    return (
      <div className="max-w-4xl mx-auto">
        <p className="text-gray-500">Источник не найден</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <Link
        to="/feeds"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Назад к источникам
      </Link>

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
            <Rss className="w-5 h-5 text-blue-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">{feed.title}</h1>
        </div>
        {feed.description && (
          <p className="text-gray-600 mb-2">{feed.description}</p>
        )}
        <p className="text-sm text-gray-500">
          {articles.length} {articles.length === 1 ? "статья" : articles.length < 5 ? "статьи" : "статей"}
        </p>
      </div>

      <div className="space-y-3">
        {articles.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <Rss className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">Статей от этого источника пока нет</p>
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
                <span className="flex items-center gap-1 text-gray-500">
                  <Clock className="w-3 h-3" />
                  {formatDistanceToNow(new Date(article.pubDate), { 
                    addSuffix: true,
                    locale: ru 
                  })}
                </span>

                <button
                  onClick={(e) => handleToggleRead(e, article.id)}
                  className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                    article.read
                      ? "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                  }`}
                >
                  {article.read ? "Прочитано" : "Непрочитано"}
                </button>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
