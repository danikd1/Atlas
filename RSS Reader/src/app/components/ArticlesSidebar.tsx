import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router";
import { X, Rss, Loader2, Calendar, BookOpen, Bookmark, FileText, CheckCheck, MessageSquare, BookText, Map } from "lucide-react";

function Tooltip({ label, children, align = "center" }: { label: string; children: React.ReactNode; align?: "left" | "center" | "right" }) {
  const posClass =
    align === "right" ? "right-0" :
    align === "left"  ? "left-0"  :
    "left-1/2 -translate-x-1/2";
  const arrowClass =
    align === "right" ? "right-2" :
    align === "left"  ? "left-2"  :
    "left-1/2 -translate-x-1/2";

  return (
    <div className="relative group/tip">
      {children}
      <div className={`absolute top-full ${posClass} mt-1.5 px-2 py-1 bg-gray-800 text-white text-xs rounded-md whitespace-nowrap opacity-0 group-hover/tip:opacity-100 transition-opacity pointer-events-none z-50 shadow-sm`}>
        <div className={`absolute bottom-full ${arrowClass} border-4 border-transparent border-b-gray-800`} />
        {label}
      </div>
    </div>
  );
}
import { ArticleSource, sourceKey } from "../types";
import { api, ApiArticleItem } from "../lib/api";
import { ArticleCard } from "./ArticleCard";
import { QAPanel } from "./QAPanel";
import { DigestPanel } from "./DigestPanel";

interface ArticlesSidebarProps {
  source: ArticleSource;
  onClose: () => void;
}

const PAGE_SIZE = 30;

// Источники без пагинации (today / saved показывают всё разом)
const NO_PAGINATION: Array<ArticleSource["kind"]> = ["today"];

function sourceTitle(source: ArticleSource): string {
  switch (source.kind) {
    case "today":
      return "Сегодня";
    case "unread":
      return "Непрочитанное";
    case "saved":
      return "Сохранённое";
    case "all":
      return "Все посты";
    case "feed":
      return source.title;
    case "topic":
      return source.title;
  }
}

function SourceIcon({ source }: { source: ArticleSource }) {
  if (source.kind === "topic") {
    return <Map className="w-4 h-4 text-blue-600 flex-shrink-0" />;
  }
  if (source.kind === "feed") {
    return source.favicon_url ? (
      <img
        src={source.favicon_url}
        alt=""
        className="w-5 h-5 rounded flex-shrink-0"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    ) : (
      <Rss className="w-4 h-4 text-gray-400 flex-shrink-0" />
    );
  }
  const iconClass = "w-4 h-4 text-blue-600 flex-shrink-0";
  switch (source.kind) {
    case "today":
      return <Calendar className={iconClass} />;
    case "unread":
      return <BookOpen className={iconClass} />;
    case "saved":
      return <Bookmark className={iconClass} />;
    case "all":
      return <FileText className={iconClass} />;
  }
}

async function fetchArticles(
  source: ArticleSource,
  page: number
): Promise<ApiArticleItem[]> {
  switch (source.kind) {
    case "today":
      return api.getTodayArticles();
    case "unread":
      return api.getUnreadArticles(page);
    case "saved":
      return api.getBookmarks(page);
    case "all":
      return api.getAllArticles(page);
    case "feed": {
      const ids = source.feedIds && source.feedIds.length > 0
        ? source.feedIds
        : [parseInt(source.feedId)];
      return ids.length > 1
        ? api.getArticlesByFeedIds(ids, page)
        : api.getFeedArticles(ids[0], page, false);
    }
    case "topic":
      return api.getCollectionArticles(source.collectionId, page);
  }
}

export function ArticlesSidebar({ source, onClose }: ArticlesSidebarProps) {
  const location = useLocation();
  const [articles, setArticles] = useState<ApiArticleItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const key = sourceKey(source);
  const keyRef = useRef(key);

  // Определяем id открытой статьи по URL /article/:id
  const activeArticleMatch = location.pathname.match(/^\/article\/(\d+)$/);
  const activeArticleId = activeArticleMatch ? parseInt(activeArticleMatch[1]) : null;

  // Перезагрузка при смене source
  useEffect(() => {
    keyRef.current = key;
    setPage(1);
    loadInitial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Обновление при глобальных событиях (сбор лент, изменение закладок и т.п.)
  useEffect(() => {
    const handler = () => loadInitial();
    window.addEventListener("feeds-updated", handler);
    return () => window.removeEventListener("feeds-updated", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const loadInitial = async () => {
    setIsLoading(true);
    try {
      const data = await fetchArticles(source, 1);
      setArticles(data);
      setPage(1);
      setHasMore(
        !NO_PAGINATION.includes(source.kind) && data.length === PAGE_SIZE
      );
    } catch (e) {
      console.error("Ошибка загрузки статей:", e);
      setArticles([]);
      setHasMore(false);
    } finally {
      setIsLoading(false);
    }
  };

  const loadMore = async () => {
    if (isLoadingMore || !hasMore) return;
    setIsLoadingMore(true);
    try {
      const next = page + 1;
      const data = await fetchArticles(source, next);
      setArticles((prev) => [...prev, ...data]);
      setPage(next);
      setHasMore(data.length === PAGE_SIZE);
    } catch (e) {
      console.error("Ошибка пагинации:", e);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleArticleClick = async (article: ApiArticleItem) => {
    if (!article.is_read) {
      setArticles((prev) =>
        prev.map((a) => (a.id === article.id ? { ...a, is_read: true } : a))
      );
      try {
        await api.markArticleRead(article.link);
        window.dispatchEvent(new CustomEvent("feeds-updated"));
      } catch (e) {
        console.error("Ошибка пометки прочитанной:", e);
      }
    }
  };

  const handleReadChange = (id: number, isRead: boolean) => {
    // На странице "Непрочитанное" при пометке прочитанным — убираем из списка
    if (source.kind === "unread" && isRead) {
      setArticles((prev) => prev.filter((a) => a.id !== id));
      return;
    }
    setArticles((prev) =>
      prev.map((a) => (a.id === id ? { ...a, is_read: isRead } : a))
    );
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    // На странице "Сохранённое" при снятии закладки — убираем из списка
    if (source.kind === "saved" && !saved) {
      setArticles((prev) => prev.filter((a) => a.id !== id));
      return;
    }
    setArticles((prev) =>
      prev.map((a) => (a.id === id ? { ...a, is_saved: saved } : a))
    );
  };

  const handleMarkAllRead = async () => {
    if (source.kind !== "feed") return;
    const ids =
      source.feedIds && source.feedIds.length > 0
        ? source.feedIds
        : [parseInt(source.feedId)];
    try {
      await Promise.all(ids.map((id) => api.markFeedAllRead(id)));
      setArticles((prev) => prev.map((a) => ({ ...a, is_read: true })));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
    } catch (e) {
      console.error("Ошибка пометки всех прочитанными:", e);
    }
  };

  const unreadCount = articles.filter((a) => !a.is_read).length;
  const isMultiFeed =
    source.kind === "feed" && source.feedIds && source.feedIds.length > 1;

  // QA / Digest panel state — только для лент (feed)
  type ActivePanel = "qa" | "digest" | null;
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);

  // feedIds для QA/Digest — числовые ID
  const feedIdsForPanel: number[] =
    source.kind === "feed"
      ? (source.feedIds && source.feedIds.length > 0
          ? source.feedIds
          : [parseInt(source.feedId)])
      : source.kind === "topic"
      ? [...new Set(articles.map((a) => a.feed_id).filter((id): id is number => id !== null))]
      : [];

  const togglePanel = (panel: ActivePanel) =>
    setActivePanel((prev) => (prev === panel ? null : panel));

  return (
    <aside className="w-full bg-white border-l border-gray-200 h-full overflow-hidden flex-shrink-0 flex flex-col">
      {/* Заголовок */}
      <div className="bg-white border-b border-gray-200 p-4 z-10 flex-shrink-0">
        {/* Строка 1: иконка + название + кнопка закрыть */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <SourceIcon source={source} />
            <h2 className="font-semibold text-gray-900 text-sm truncate">
              {sourceTitle(source)}
            </h2>
          </div>
          <Tooltip label="Закрыть" align="right">
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
            >
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </Tooltip>
        </div>

        {/* Строка 2: статистика + кнопки действий */}
        <div className="flex items-center justify-between mt-1.5">
          {!isLoading && articles.length > 0 ? (
            <p className="text-xs text-gray-400">
              {unreadCount > 0 ? `${unreadCount} непрочитанных · ` : ""}
              {articles.length} статей
            </p>
          ) : (
            <span />
          )}

          {(source.kind === "feed" || source.kind === "topic") && (
            <div className="flex items-center gap-0.5">
              <Tooltip label="Спросить" align="right">
                <button
                  onClick={() => togglePanel("qa")}
                  className={`p-1.5 rounded-lg transition-colors ${activePanel === "qa" ? "bg-blue-100 text-blue-600" : "hover:bg-gray-100 text-gray-400"}`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                </button>
              </Tooltip>
              <Tooltip label="Дайджест" align="right">
                <button
                  onClick={() => togglePanel("digest")}
                  className={`p-1.5 rounded-lg transition-colors ${activePanel === "digest" ? "bg-blue-100 text-blue-600" : "hover:bg-gray-100 text-gray-400"}`}
                >
                  <BookText className="w-3.5 h-3.5" />
                </button>
              </Tooltip>
              {unreadCount > 0 && (
                <Tooltip label="Пометить все прочитанными" align="right">
                  <button
                    onClick={handleMarkAllRead}
                    className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors text-gray-400"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                  </button>
                </Tooltip>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Список статей + QA/Digest */}
      <div className="flex-1 overflow-y-auto">
        {activePanel === "qa" && (feedIdsForPanel.length > 0 || source.kind === "topic") && (
          <QAPanel
            feedIds={feedIdsForPanel}
            collectionId={source.kind === "topic" ? source.collectionId : undefined}
          />
        )}
        {activePanel === "digest" && (feedIdsForPanel.length > 0 || source.kind === "topic") && (
          <DigestPanel
            feedIds={feedIdsForPanel}
            collectionId={source.kind === "topic" ? source.collectionId : undefined}
          />
        )}
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
          <>
            {articles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                variant="sidebar"
                isActive={article.id === activeArticleId}
                onClick={handleArticleClick}
                onReadChange={handleReadChange}
                onSavedChange={handleSavedChange}
                showSource={true}
              />
            ))}
            {hasMore && (
              <div className="p-4">
                <button
                  onClick={loadMore}
                  disabled={isLoadingMore}
                  className="w-full py-2 text-sm text-blue-600 hover:bg-blue-50 rounded-md transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isLoadingMore && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {isLoadingMore ? "Загружаем..." : "Загрузить ещё"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
