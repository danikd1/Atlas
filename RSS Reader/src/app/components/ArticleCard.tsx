import { useState } from "react";
import { Link } from "react-router";
import { Clock } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { ApiArticleItem } from "../lib/api";
import { StarButton } from "./StarButton";
import { SummarizeButton } from "./SummarizeButton";
import { SummaryPanel } from "./SummaryPanel";
import { ReadButton } from "./ReadButton";

// ─── Shared article card ────────────────────────────────────────────────────
//
// variant="card"    — full card (TodayPage, UnreadPage, ArticlesPage)
// variant="row"     — compact row with unread dot (FeedArticlesPage)
// variant="sidebar" — minimal row (ArticlesSidebar)

interface ArticleCardProps {
  article: ApiArticleItem;
  variant?: "card" | "row" | "sidebar";
  /** Custom time formatter. Defaults to relative time. */
  formatTime?: (dateStr: string) => string;
  onSavedChange?: (id: number, saved: boolean) => void;
  onReadChange?: (id: number, isRead: boolean) => void;
  /** Extra click handler (e.g. optimistic read update on link click) */
  onClick?: (article: ApiArticleItem) => void;
  /** Show source name prefix (used in multi-feed sidebars) */
  showSource?: boolean;
  /** Подсветка активной (открытой сейчас) карточки. Используется в sidebar-варианте. */
  isActive?: boolean;
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    return formatDistanceToNow(new Date(dateStr), { addSuffix: true, locale: ru });
  } catch {
    return "";
  }
}

export function ArticleCard({
  article,
  variant = "card",
  formatTime,
  onSavedChange,
  onReadChange,
  onClick,
  showSource = false,
  isActive = false,
}: ArticleCardProps) {
  // Состояние резюме живёт здесь — страницам не нужно знать про него
  const [summaryText, setSummaryText] = useState<string | null>(null);
  const [summaryVisible, setSummaryVisible] = useState(false);

  const timeStr = article.published_at
    ? (formatTime ? formatTime(article.published_at) : relativeTime(article.published_at))
    : "";

  const handleSavedToggle = (saved: boolean) => {
    onSavedChange?.(article.id, saved);
  };

  const handleReadToggle = (isRead: boolean) => {
    onReadChange?.(article.id, isRead);
    window.dispatchEvent(new CustomEvent("feeds-updated"));
  };

  const handleSummaryLoad = (text: string) => {
    setSummaryText(text);
    setSummaryVisible(true);
  };

  const handleSummaryToggle = () => {
    setSummaryVisible((v) => !v);
  };

  // Кнопки действий — общий фрагмент для всех вариантов
  const actionButtons = (
    <>
      <SummarizeButton
        articleId={article.id}
        hasSummary={summaryText !== null}
        summaryVisible={summaryVisible}
        onLoad={handleSummaryLoad}
        onToggle={handleSummaryToggle}
        size="sm"
      />
      <StarButton
        link={article.link}
        isSaved={article.is_saved}
        onToggle={handleSavedToggle}
        size="sm"
      />
    </>
  );

  // Интерактивная точка прочитано/непрочитано
  const readDot = (
    <ReadButton
      link={article.link}
      isRead={article.is_read}
      onToggle={handleReadToggle}
    />
  );

  // ── card variant ────────────────────────────────────────────────────────
  if (variant === "card") {
    return (
      <div>
        <Link
          to={`/article/${article.id}`}
          onClick={() => onClick?.(article)}
          className="block bg-white rounded-lg shadow-sm border border-gray-200 p-5 hover:shadow-md hover:border-blue-200 transition-all"
        >
          <div className="flex items-start gap-3">
            <div className="mt-1.5 flex-shrink-0">
              {readDot}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className={`text-lg font-medium leading-snug mb-2 ${article.is_read ? "text-gray-500" : "text-gray-900"}`}>
                {article.title ?? "Без заголовка"}
              </h3>

              {article.summary && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">{article.summary}</p>
              )}

              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  {article.source && (
                    <span className="font-medium text-blue-600">{article.source}</span>
                  )}
                  {timeStr && (
                    <span className="flex items-center gap-1 text-gray-500">
                      <Clock className="w-3 h-3" />
                      {timeStr}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {actionButtons}
                </div>
              </div>
            </div>
          </div>
        </Link>
        {summaryVisible && summaryText && (
          <SummaryPanel text={summaryText} />
        )}
      </div>
    );
  }

  // ── row variant (FeedArticlesPage) ──────────────────────────────────────
  if (variant === "row") {
    return (
      <div>
        <Link
          to={`/article/${article.id}`}
          onClick={() => onClick?.(article)}
          className={`block bg-white rounded-lg border p-4 hover:shadow-md hover:border-blue-200 transition-all ${
            article.is_read ? "border-gray-200" : "border-gray-300"
          }`}
        >
          <div className="flex items-start gap-3">
            <div className="mt-1.5 flex-shrink-0">
              {readDot}
            </div>

            <div className="flex-1 min-w-0">
              <h3 className={`text-base mb-1 ${article.is_read ? "font-normal text-gray-500" : "font-semibold text-gray-900"}`}>
                {article.title ?? "Без заголовка"}
              </h3>
              {article.summary && (
                <p className="text-sm text-gray-600 line-clamp-2 mb-2">{article.summary}</p>
              )}
              {timeStr && (
                <div className="flex items-center gap-1 text-xs text-gray-400">
                  <Clock className="w-3 h-3" />
                  <span>{timeStr}</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              {actionButtons}
            </div>
          </div>
        </Link>
        {summaryVisible && summaryText && (
          <SummaryPanel text={summaryText} />
        )}
      </div>
    );
  }

  // ── sidebar variant (ArticlesSidebar) ───────────────────────────────────
  // Для этого варианта кнопки action (лампочка + звезда) вынесены в нижний
  // правый угол и делаются чуть крупнее, а активная карточка (открытая в
  // reader) подсвечивается голубым + синяя полоска слева.
  const sidebarActionButtons = (
    <>
      <SummarizeButton
        articleId={article.id}
        hasSummary={summaryText !== null}
        summaryVisible={summaryVisible}
        onLoad={handleSummaryLoad}
        onToggle={handleSummaryToggle}
        size="md"
        strokeWidth={3}
      />
      <StarButton
        link={article.link}
        isSaved={article.is_saved}
        onToggle={handleSavedToggle}
        size="md"
        strokeWidth={3}
      />
    </>
  );

  return (
    <div className="relative group/sidebar-card">
      {isActive && (
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500 z-10" />
      )}
      <Link
        to={`/article/${article.id}`}
        onClick={() => onClick?.(article)}
        className={`block px-4 py-3 transition-colors border-b border-gray-100 last:border-0 ${
          isActive ? "bg-blue-50" : "hover:bg-gray-50"
        }`}
      >
        <div className="flex items-start gap-2">
          <div className="mt-1.5 flex-shrink-0">
            {readDot}
          </div>

          <div className="flex-1 min-w-0">
            <h3 className={`text-sm mb-1 line-clamp-2 leading-snug ${
              isActive
                ? "font-bold text-blue-600"
                : article.is_read
                  ? "font-normal text-gray-500"
                  : "font-semibold text-gray-900"
            }`}>
              {article.title ?? "Без заголовка"}
            </h3>
            {article.summary && (
              <p className="text-xs text-gray-500 line-clamp-2 mb-2 leading-relaxed">
                {article.summary}
              </p>
            )}

            {/* Нижняя строка: источник/время слева, кнопки справа */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1 text-xs text-gray-400 min-w-0">
                {showSource && article.source && (
                  <span className="text-blue-500 font-medium truncate">{article.source}</span>
                )}
                {showSource && article.source && timeStr && <span>·</span>}
                {timeStr && <span className="truncate">{timeStr}</span>}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover/sidebar-card:opacity-100 transition-opacity">
                {sidebarActionButtons}
              </div>
            </div>
          </div>
        </div>
      </Link>
      {summaryVisible && summaryText && (
        <SummaryPanel text={summaryText} />
      )}
    </div>
  );
}
