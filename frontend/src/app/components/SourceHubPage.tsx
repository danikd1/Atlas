import { useState, useEffect } from "react";
import { useParams, useNavigate, useOutletContext } from "react-router";
import { ArrowLeft, Rss, Loader2, CheckCircle2, Circle } from "lucide-react";
import { api, ApiCatalogFeed } from "../lib/api";
import { OutletCtx, sourceKey } from "../types";

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

/** Человекочитаемое название домена для заголовка */
function formatDomainName(domain: string): string {
  const map: Record<string, string> = {
    "habr.com": "Habr",
  };
  if (map[domain]) return map[domain];
  return domain.replace(/^www\./, "").split(".")[0];
}

export function SourceHubPage() {
  const { feedUrl } = useParams<{ feedUrl: string }>();
  const navigate = useNavigate();

  const domain = feedUrl ? decodeURIComponent(feedUrl) : "";

  const context = useOutletContext<OutletCtx | undefined>();
  const setSelectedSource = context?.setSelectedSource;
  const activeKey = sourceKey(context?.selectedSource ?? null);

  const [feeds, setFeeds] = useState<ApiCatalogFeed[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  // per-feed submitting
  const [submittingIds, setSubmittingIds] = useState<Set<number>>(new Set());
  // per-category "subscribe/unsubscribe all" submitting
  const [submittingCats, setSubmittingCats] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadFeeds();
  }, [domain]);

  const loadFeeds = async () => {
    setIsLoading(true);
    try {
      const catalog = await api.getCatalog();
      setFeeds(catalog.filter((f) => getDomain(f.url) === domain));
    } catch (e) {
      console.error("Ошибка загрузки лент:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const silentReload = async () => {
    try {
      const catalog = await api.getCatalog();
      setFeeds(catalog.filter((f) => getDomain(f.url) === domain));
    } catch {}
  };

  // ── Одиночная подписка ──────────────────────────────────────────
  const handleSubscribe = async (feed: ApiCatalogFeed) => {
    if (submittingIds.has(feed.id)) return;
    setSubmittingIds((prev) => new Set(prev).add(feed.id));
    try {
      await api.addFeed({ url: feed.url, name: feed.name, favicon_url: feed.favicon_url, description: feed.description, category: feed.category });
      setFeeds((prev) => prev.map((f) => f.id === feed.id ? { ...f, is_subscribed: true } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReload, 1500);
    } catch (e) {
      console.error("Ошибка при подписке:", e);
    } finally {
      setSubmittingIds((prev) => { const s = new Set(prev); s.delete(feed.id); return s; });
    }
  };

  const handleUnsubscribe = async (feed: ApiCatalogFeed) => {
    if (submittingIds.has(feed.id)) return;
    setSubmittingIds((prev) => new Set(prev).add(feed.id));
    try {
      await api.deleteFeed(feed.id);
      setFeeds((prev) => prev.map((f) => f.id === feed.id ? { ...f, is_subscribed: false } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReload, 1500);
    } catch (e) {
      console.error("Ошибка при отписке:", e);
    } finally {
      setSubmittingIds((prev) => { const s = new Set(prev); s.delete(feed.id); return s; });
    }
  };

  // ── Подписка/отписка на всю категорию ──────────────────────────
  const handleSubscribeAll = async (category: string, catFeeds: ApiCatalogFeed[]) => {
    if (submittingCats.has(category)) return;
    const toSubscribe = catFeeds.filter((f) => !f.is_subscribed);
    if (toSubscribe.length === 0) return;
    setSubmittingCats((prev) => new Set(prev).add(category));
    try {
      await api.addFeedsBatch(
        toSubscribe.map((f) => ({ url: f.url, name: f.name, favicon_url: f.favicon_url, description: f.description, category: f.category }))
      );
      const ids = new Set(toSubscribe.map((f) => f.id));
      setFeeds((prev) => prev.map((f) => ids.has(f.id) ? { ...f, is_subscribed: true } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReload, 1500);
    } catch (e) {
      console.error("Ошибка при подписке на категорию:", e);
    } finally {
      setSubmittingCats((prev) => { const s = new Set(prev); s.delete(category); return s; });
    }
  };

  const handleUnsubscribeAll = async (category: string, catFeeds: ApiCatalogFeed[]) => {
    if (submittingCats.has(category)) return;
    const toUnsub = catFeeds.filter((f) => f.is_subscribed);
    if (toUnsub.length === 0) return;
    setSubmittingCats((prev) => new Set(prev).add(category));
    try {
      await Promise.all(toUnsub.map((f) => api.deleteFeed(f.id)));
      const ids = new Set(toUnsub.map((f) => f.id));
      setFeeds((prev) => prev.map((f) => ids.has(f.id) ? { ...f, is_subscribed: false } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReload, 1500);
    } catch (e) {
      console.error("Ошибка при отписке от категории:", e);
    } finally {
      setSubmittingCats((prev) => { const s = new Set(prev); s.delete(category); return s; });
    }
  };

  // ── Группировка по категориям ───────────────────────────────────
  const categoryOrder = ["Engineering", "AI & ML", "Management", "Cloud & DevOps", "Data", "Security", "Design", "Tech News", "Case Studies", "Tools", "Other"];

  const byCategory = new Map<string, ApiCatalogFeed[]>();
  feeds.forEach((f) => {
    const cat = f.category ?? "Other";
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat)!.push(f);
  });

  // Сортируем категории: сначала по categoryOrder, потом остальные алфавитно
  const sortedCategories = Array.from(byCategory.keys()).sort((a, b) => {
    const ai = categoryOrder.indexOf(a);
    const bi = categoryOrder.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.localeCompare(b);
  });

  const sourceName = formatDomainName(domain);
  const subscribedTotal = feeds.filter((f) => f.is_subscribed).length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="mb-6 flex-shrink-0">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Назад к источникам</span>
        </button>

        <div className="flex items-end gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{sourceName}</h1>
            {!isLoading && (
              <p className="text-gray-500 text-sm mt-1">
                {feeds.length} лент · {sortedCategories.length} категорий · {subscribedTotal} подписок
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Kanban columns */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin mr-3" />
          Загрузка...
        </div>
      ) : feeds.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p>Источник не найден</p>
          <button onClick={() => navigate("/")} className="mt-4 text-blue-600 hover:text-blue-700">
            Вернуться на главную
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto pb-4 -mx-4 px-4">
          <div className="flex gap-4" style={{ minWidth: "max-content" }}>
            {sortedCategories.map((category) => {
              const catFeeds = byCategory.get(category)!;
              const subscribedCount = catFeeds.filter((f) => f.is_subscribed).length;
              const allSubscribed = subscribedCount === catFeeds.length;
              const isCatSubmitting = submittingCats.has(category);

              return (
                <div
                  key={category}
                  className="w-64 flex-shrink-0 bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col"
                >
                  {/* Column header */}
                  <div className="p-4 border-b border-gray-100">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h2 className="font-semibold text-gray-900 text-sm">{category}</h2>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {subscribedCount}/{catFeeds.length} подписок
                        </p>
                      </div>
                      {/* Прогресс-дуга */}
                      <div className="relative w-8 h-8 flex-shrink-0">
                        <svg className="w-8 h-8 -rotate-90" viewBox="0 0 32 32">
                          <circle cx="16" cy="16" r="12" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                          <circle
                            cx="16" cy="16" r="12"
                            fill="none"
                            stroke={allSubscribed ? "#2563eb" : "#93c5fd"}
                            strokeWidth="3"
                            strokeDasharray={`${2 * Math.PI * 12}`}
                            strokeDashoffset={`${2 * Math.PI * 12 * (1 - subscribedCount / catFeeds.length)}`}
                            strokeLinecap="round"
                          />
                        </svg>
                      </div>
                    </div>

                    {/* Subscribe / Unsubscribe all */}
                    <button
                      disabled={isCatSubmitting}
                      onClick={() =>
                        allSubscribed
                          ? handleUnsubscribeAll(category, catFeeds)
                          : handleSubscribeAll(category, catFeeds)
                      }
                      className={`w-full text-xs py-1.5 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                        allSubscribed
                          ? "bg-gray-100 text-gray-600 hover:bg-red-50 hover:text-red-600"
                          : "bg-blue-600 text-white hover:bg-blue-700"
                      }`}
                    >
                      {isCatSubmitting ? (
                        <Loader2 className="w-3 h-3 animate-spin inline" />
                      ) : allSubscribed ? (
                        "Отписаться от всех"
                      ) : subscribedCount > 0 ? (
                        `Подписаться на остальные (${catFeeds.length - subscribedCount})`
                      ) : (
                        `Подписаться на все (${catFeeds.length})`
                      )}
                    </button>
                  </div>

                  {/* Feed list */}
                  <div className="flex-1 overflow-y-auto divide-y divide-gray-50 max-h-[60vh]">
                    {catFeeds.map((feed) => {
                      const isSubmitting = submittingIds.has(feed.id);
                      const isActive = activeKey === `feed:${feed.id}`;
                      const shortName = feed.name.replace(/^[^:]+:\s*/i, "");
                      return (
                        <div
                          key={feed.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (isActive) {
                              setSelectedSource?.(null);
                            } else {
                              setSelectedSource?.({
                                kind: "feed",
                                feedId: feed.id.toString(),
                                title: feed.name,
                                favicon_url: feed.favicon_url ?? undefined,
                              });
                            }
                          }}
                          className={`flex items-start gap-2 px-4 py-2.5 cursor-pointer transition-colors ${
                            isActive
                              ? "bg-blue-100 border-l-2 border-blue-500"
                              : feed.is_subscribed
                              ? "bg-blue-50/40 hover:bg-blue-50"
                              : "hover:bg-gray-50"
                          }`}
                        >
                          {/* Subscribe toggle */}
                          <button
                            disabled={isSubmitting}
                            onClick={(e) => {
                              e.stopPropagation();
                              feed.is_subscribed ? handleUnsubscribe(feed) : handleSubscribe(feed);
                            }}
                            className="flex-shrink-0 mt-0.5 text-gray-400 hover:text-blue-600 transition-colors disabled:opacity-40"
                            title={feed.is_subscribed ? "Отписаться" : "Подписаться"}
                          >
                            {isSubmitting ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : feed.is_subscribed ? (
                              <CheckCircle2 className="w-4 h-4 text-blue-600" />
                            ) : (
                              <Circle className="w-4 h-4" />
                            )}
                          </button>

                          {/* Feed name + description */}
                          <div className="flex-1 min-w-0">
                            <p
                              className={`text-sm truncate ${
                                feed.is_subscribed ? "text-gray-900 font-medium" : "text-gray-700"
                              }`}
                              title={feed.name}
                            >
                              {shortName}
                            </p>
                            {feed.description && (
                              <p className="text-xs text-gray-400 truncate mt-0.5" title={feed.description}>
                                {feed.description}
                              </p>
                            )}
                          </div>

                          {/* Favicon */}
                          {feed.favicon_url ? (
                            <img
                              src={feed.favicon_url}
                              alt=""
                              className="w-3.5 h-3.5 rounded flex-shrink-0 opacity-50 mt-0.5"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                            />
                          ) : (
                            <Rss className="w-3 h-3 text-gray-300 flex-shrink-0 mt-1" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
