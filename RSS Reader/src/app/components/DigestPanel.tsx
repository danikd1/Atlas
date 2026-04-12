import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { Loader2, ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { digestCache, digestCacheKey, type CachedDigest } from "../lib/digestCache";

interface DigestPanelProps {
  feedIds: number[];
  collectionId?: number;
}

type Period = "day" | "week" | "month";

const PERIOD_LABELS: Record<Period, string> = {
  day: "День",
  week: "Неделя",
  month: "Месяц",
};

const SECTION_LABELS: Record<string, string> = {
  key_trends: "Тренды",
  methods: "Методы и подходы",
  tools: "Инструменты",
  case_studies: "Кейсы",
};

function periodToDates(period: Period): { from_date: string; to_date: string } {
  const now = new Date();
  const to_date = now.toISOString();
  const from = new Date(now);
  if (period === "day") from.setDate(now.getDate() - 1);
  else if (period === "week") from.setDate(now.getDate() - 7);
  else from.setMonth(now.getMonth() - 1);
  return { from_date: from.toISOString(), to_date };
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function SectionBlock({
  title,
  items,
  defaultExpanded = true,
  onArticleClick,
}: {
  title: string;
  items: CachedDigest["sections"][string];
  defaultExpanded?: boolean;
  onArticleClick: (articleId: number) => void;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  if (!items.length) return null;
  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="text-xs font-semibold text-gray-600">{title}</span>
        <div className="flex items-center gap-2">
          {!expanded && items.length > 0 && (
            <span className="text-xs text-gray-400">{items.length}</span>
          )}
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
          )}
        </div>
      </button>
      {expanded && (
        <div className="divide-y divide-gray-50">
          {items.map((item, i) => (
            <div key={i} className="px-3 py-2.5 bg-white">
              {item.label && (
                <p className="text-xs font-medium text-gray-800 mb-1">{item.label}</p>
              )}
              {item.description && (
                <p className="text-xs text-gray-500 leading-relaxed mb-2">{item.description}</p>
              )}
              {item.articles.slice(0, 3).map((a) => (
                <button
                  key={a.link}
                  onClick={() => onArticleClick(a.article_id)}
                  className="w-full text-left flex items-start justify-between gap-2 py-1 hover:text-blue-700 group"
                >
                  <span className="text-xs text-blue-600 group-hover:text-blue-800 group-hover:underline truncate leading-snug">
                    {a.title || a.link}
                  </span>
                  {a.published_at && (
                    <span className="text-xs text-gray-300 flex-shrink-0 mt-0.5">
                      {formatDate(a.published_at)}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function DigestPanel({ feedIds, collectionId }: DigestPanelProps) {
  const navigate = useNavigate();
  const [period, setPeriod] = useState<Period>("week");
  const [isLoading, setIsLoading] = useState(false);
  const [digest, setDigest] = useState<CachedDigest | null>(null);
  const [error, setError] = useState<string | null>(null);
  // autoLoaded = восстановлен из кэша при смене ленты → секции свёрнуты
  const [autoLoaded, setAutoLoaded] = useState(false);
  const [visible, setVisible] = useState(false); // показан ли результат

  const feedIdsKey = [...feedIds].sort((a, b) => a - b).join(",");

  // При смене ленты — ищем кэш для текущего периода, потом для остальных
  useEffect(() => {
    const periods: Period[] = [period, "week", "month", "day"];
    for (const p of periods) {
      const key = digestCacheKey(feedIds, p);
      if (digestCache.has(key)) {
        setDigest(digestCache.get(key));
        setPeriod(p);
        setAutoLoaded(true);
        setError(null);
        return;
      }
    }
    // Нет кэша для этой ленты
    setDigest(null);
    setAutoLoaded(false);
    setVisible(false);
    setError(null);
  }, [feedIdsKey]);

  const buildDigest = async (forceRefresh = false) => {
    if (isLoading) return;
    const key = digestCacheKey(feedIds, period);

    if (!forceRefresh && digestCache.has(key)) {
      setDigest(digestCache.get(key));
      setAutoLoaded(false);
      setVisible(true);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    setAutoLoaded(false);
    setVisible(false);

    try {
      const { from_date, to_date } = periodToDates(period);
      const result = await api.feedDigest({ feed_ids: feedIds, collection_id: collectionId, from_date, to_date });
      const data = result as CachedDigest;
      digestCache.set(key, data);
      setDigest(data);
      setVisible(true);
    } catch (e: any) {
      setError(e.message || "Ошибка запроса");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePeriodChange = (p: Period) => {
    setPeriod(p);
    const key = digestCacheKey(feedIds, p);
    if (digestCache.has(key)) {
      setDigest(digestCache.get(key));
      setAutoLoaded(false);
      setVisible(true);
      setError(null);
    } else {
      setDigest(null);
      setAutoLoaded(false);
      setVisible(false);
    }
  };

  const isCached = digest !== null && digestCache.has(digestCacheKey(feedIds, period));
  const totalItems = digest
    ? Object.values(digest.sections).reduce((s, items) => s + items.length, 0)
    : 0;

  return (
    <div className="border-t border-gray-100 bg-gray-50">
      <div className="p-3 flex items-center gap-2">
        <div className="flex rounded-lg border border-gray-200 overflow-hidden flex-shrink-0">
          {(["day", "week", "month"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => handlePeriodChange(p)}
              className={`px-2.5 py-1.5 text-xs transition-colors ${
                period === p
                  ? "bg-blue-600 text-white"
                  : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              {PERIOD_LABELS[p]}
            </button>
          ))}
        </div>
        <button
          onClick={() => isCached ? setVisible(!visible) : buildDigest(false)}
          disabled={isLoading}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" />Составляем...</>
          ) : isCached && visible ? (
            "Скрыть дайджест"
          ) : isCached ? (
            "Показать дайджест"
          ) : (
            "Создать дайджест"
          )}
        </button>
        {isCached && !isLoading && (
          <button
            onClick={() => buildDigest(true)}
            className="flex-shrink-0 p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
            title="Пересоздать дайджест"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {error && (
        <div className="mx-3 mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {digest && visible && (
        <div className="px-3 pb-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-400">
              {digest.article_count} статей · {totalItems} тем
            </p>
            {isCached && (
              <p className="text-xs text-gray-300 italic">из кэша</p>
            )}
          </div>
          {Object.entries(SECTION_LABELS).map(([sectionKey, label]) => (
            <SectionBlock
              key={`${sectionKey}-${autoLoaded}`}
              title={label}
              items={digest.sections[sectionKey] || []}
              defaultExpanded={!autoLoaded}
              onArticleClick={(id) => navigate(`/article/${id}`)}
            />
          ))}
          {totalItems === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">
              За этот период не найдено статей для дайджеста
            </p>
          )}
        </div>
      )}
    </div>
  );
}
