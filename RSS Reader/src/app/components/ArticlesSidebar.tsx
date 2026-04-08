import { useState, useEffect } from "react";
import { Link } from "react-router";
import { X } from "lucide-react";
import { RSSArticle, RSSFeed } from "../types";
import { getArticles, toggleArticleRead, getFeeds } from "../lib/storage";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale/ru";

interface ArticlesSidebarProps {
  feed: RSSFeed;
  onClose: () => void;
}

export function ArticlesSidebar({ feed, onClose }: ArticlesSidebarProps) {
  const [articles, setArticles] = useState<RSSArticle[]>([]);

  const loadArticles = () => {
    const allArticles = getArticles();
    
    // Filter by feed id OR by matching feed URL (for temp feeds)
    const feedArticles = allArticles.filter((a) => {
      if (a.feedId === feed.id) return true;
      
      // For temp feeds, try to match by URL
      if (feed.id.startsWith('temp-')) {
        const allFeeds = getFeeds();
        const matchingFeed = allFeeds.find(f => f.url === feed.url);
        return matchingFeed && a.feedId === matchingFeed.id;
      }
      
      return false;
    });
    
    // Sort by date, newest first
    feedArticles.sort((a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime());
    setArticles(feedArticles);
  };

  useEffect(() => {
    loadArticles();
  }, [feed.id]);

  const unreadCount = articles.filter((a) => !a.read).length;

  const handleToggleRead = (articleId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleRead(articleId);
    loadArticles();
  };

  return (
    <aside className="w-96 bg-white border-l border-gray-200 h-[calc(100vh-4rem)] overflow-y-auto flex-shrink-0">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 z-10">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h2 className="font-semibold text-gray-900 text-base mb-1 truncate">{feed.title}</h2>
            {articles.length > 0 && (
              <p className="text-xs text-gray-500">
                {unreadCount} {unreadCount === 1 ? "новая" : unreadCount > 1 && unreadCount < 5 ? "новые" : "новых"} • {articles.length} всего
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            title="Закрыть"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
      </div>

      {/* Articles List */}
      <div className="py-2">
        {articles.length === 0 ? (
          <div className="text-center py-12 px-4">
            <p className="text-sm text-gray-400">Статей пока нет</p>
          </div>
        ) : (
          articles.map((article) => (
            <Link
              key={article.id}
              to={`/article/${article.id}`}
              className="block px-4 py-3 hover:bg-gray-50 transition-colors group"
            >
              <div className="flex items-start gap-3">
                {/* Read indicator dot */}
                <button
                  onClick={(e) => handleToggleRead(article.id, e)}
                  className="flex-shrink-0 mt-1.5"
                  title={article.read ? "Отметить как непрочитанное" : "Отметить как прочитанное"}
                >
                  <div className={`w-2 h-2 rounded-full transition-colors ${
                    article.read ? "bg-transparent border border-gray-300" : "bg-blue-500"
                  }`} />
                </button>
                
                <div className="flex-1 min-w-0">
                  <h3 className={`text-sm font-medium mb-1 line-clamp-2 leading-snug ${
                    article.read ? "text-gray-500" : "text-gray-900"
                  }`}>
                    {article.title}
                  </h3>
                  
                  {article.description && (
                    <p className="text-xs text-gray-400 line-clamp-2 mb-2 leading-relaxed">
                      {article.description}
                    </p>
                  )}
                  
                  <div className="text-xs text-gray-400">
                    {formatDistanceToNow(new Date(article.pubDate), {
                      addSuffix: false,
                      locale: ru,
                    }).replace('около ', '')}
                  </div>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </aside>
  );
}