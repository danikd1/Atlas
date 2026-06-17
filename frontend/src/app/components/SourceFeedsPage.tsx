import { useState, useEffect } from "react";
import { useParams, useNavigate, useOutletContext } from "react-router";
import { ArrowLeft, Rss, TrendingUp, Users, BarChart3, Clock, Loader2, CheckCircle2, Circle } from "lucide-react";
import { api, ApiCatalogFeed } from "../lib/api";
import { OutletCtx, sourceKey } from "../types";

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function FeedIcon({ faviconUrl, category }: { faviconUrl: string | null; category: string | null }) {
  if (faviconUrl) {
    return (
      <img
        src={faviconUrl}
        alt=""
        className="w-4 h-4 rounded"
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
    );
  }
  if (category?.toLowerCase().includes("engineering") || category?.toLowerCase().includes("tech")) {
    return <TrendingUp className="w-4 h-4" />;
  }
  return <Rss className="w-4 h-4" />;
}

const formatSubscribers = (count: number): string => {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(0)}K`;
  return count.toString();
};

const formatRelativeTime = (dateString: string | null): string => {
  if (!dateString) return "—";
  const date = new Date(dateString);
  const now = new Date();
  const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
  if (diffInHours < 1) return `${Math.floor((now.getTime() - date.getTime()) / (1000 * 60))} мин`;
  if (diffInHours < 24) return `${diffInHours} ч`;
  return `${Math.floor(diffInHours / 24)} дн`;
};

const categoryOrder = ["Engineering", "AI & ML", "Management", "Cloud & DevOps", "Data", "Security", "Design", "Tech News", "Case Studies", "Tools", "Other"];

export function SourceFeedsPage() {
  const { feedUrl } = useParams<{ feedUrl: string }>();
  const navigate = useNavigate();
  const context = useOutletContext<OutletCtx | undefined>();
  const setSelectedSource = context?.setSelectedSource;
  const activeKey = sourceKey(context?.selectedSource ?? null);

  const [feeds, setFeeds] = useState<ApiCatalogFeed[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [submittingIds, setSubmittingIds] = useState<Set<number>>(new Set());
  const [submittingCats, setSubmittingCats] = useState<Set<string>>(new Set());

  const domain = feedUrl ? decodeURIComponent(feedUrl) : "";

  useEffect(() => { loadFeeds(); }, [domain]);

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
    if (!toSubscribe.length) return;
    setSubmittingCats((prev) => new Set(prev).add(category));
    try {
      const folderName = `${domain} · ${category}`;
      const folder = await api.createFolder(folderName, toSubscribe[0].favicon_url);
      await api.addFeedsBatch(
        toSubscribe.map((f) => ({ url: f.url, name: f.name, favicon_url: f.favicon_url, description: f.description, category: f.category, folder_id: folder.id }))
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
    if (!toUnsub.length) return;
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
  const byCategory = new Map<string, ApiCatalogFeed[]>();
  feeds.forEach((f) => {
    const cat = f.category ?? "Other";
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat)!.push(f);
  });

  const sortedCategories = Array.from(byCategory.keys()).sort((a, b) => {
    const ai = categoryOrder.indexOf(a);
    const bi = categoryOrder.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.localeCompare(b);
  });

  const subscribedTotal = feeds.filter((f) => f.is_subscribed).length;

  function commonNamePrefix(names: string[]): string | null {
    if (!names.length) return null;
    const words = names[0].split(" ");
    const prefix: string[] = [];
    for (const word of words) {
      const candidate = [...prefix, word].join(" ").toLowerCase();
      if (names.every((n) => n.toLowerCase().startsWith(candidate))) prefix.push(word);
      else break;
    }
    return prefix.length > 0 ? prefix.join(" ").replace(/[:\s]+$/, "") : null;
  }

  function formatDomainName(d: string): string {
    const stripped = d.replace(/^www\./, "");
    const parts = stripped.split(".");
    if (parts.length <= 2) return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    return parts.slice(0, -1).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
  }

  const sourceName = feeds.length > 1
    ? (commonNamePrefix(feeds.map((f) => f.name)) ?? formatDomainName(domain))
    : feeds.length === 1 ? feeds[0].name : formatDomainName(domain);

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

        <h1 className="text-3xl font-bold text-gray-900">{sourceName}</h1>
        {!isLoading && (
          <p className="text-gray-500 text-sm mt-1">
            {feeds.length} лент · {sortedCategories.length} {sortedCategories.length === 1 ? "категория" : "категорий"} · {subscribedTotal} подписок
          </p>
        )}
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
                  className="w-88 flex-shrink-0 bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col"
                  style={{ width: "22rem" }}
                >
                  {/* Column header */}
                  <div className="p-5 border-b border-gray-100">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h2 className="font-semibold text-gray-900">{category}</h2>
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
                      className={`w-full text-sm py-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
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

                  {/* Feed cards */}
                  <div className="flex-1 overflow-y-auto divide-y divide-gray-100 max-h-[65vh]">
                    {catFeeds.map((feed) => {
                      const isSubmitting = submittingIds.has(feed.id);
                      const isActive = activeKey === `feed:${feed.id}`;

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
                          className={`px-5 py-4 cursor-pointer transition-colors ${
                            isActive
                              ? "bg-blue-100 border-l-2 border-blue-500"
                              : feed.is_subscribed
                              ? "bg-blue-50/40 hover:bg-blue-50"
                              : "hover:bg-gray-50"
                          }`}
                        >
                          {/* Top row: icon + name + toggle */}
                          <div className="flex items-start gap-3">
                            {/* Favicon */}
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${feed.is_subscribed ? "bg-blue-100" : "bg-gray-100"}`}>
                              <FeedIcon faviconUrl={feed.favicon_url} category={feed.category} />
                            </div>

                            <div className="flex-1 min-w-0">
                              <p
                                className={`text-sm font-medium leading-snug ${feed.is_subscribed ? "text-gray-900" : "text-gray-700"}`}
                                title={feed.name}
                              >
                                {feed.name}
                              </p>
                              {feed.description && (
                                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed" title={feed.description}>
                                  {feed.description}
                                </p>
                              )}
                            </div>

                            <button
                              disabled={isSubmitting}
                              onClick={(e) => {
                                e.stopPropagation();
                                feed.is_subscribed ? handleUnsubscribe(feed) : handleSubscribe(feed);
                              }}
                              className="flex-shrink-0 text-gray-300 hover:text-blue-600 transition-colors disabled:opacity-40"
                              title={feed.is_subscribed ? "Отписаться" : "Подписаться"}
                            >
                              {isSubmitting ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                              ) : feed.is_subscribed ? (
                                <CheckCircle2 className="w-5 h-5 text-blue-600" />
                              ) : (
                                <Circle className="w-5 h-5" />
                              )}
                            </button>
                          </div>

                          {/* Stats row */}
                          <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
                            <span className="flex items-center gap-1" title="Подписчики">
                              <Users className="w-3.5 h-3.5" />
                              {formatSubscribers(feed.subscribers)}
                            </span>
                            <span className="flex items-center gap-1" title="Постов в неделю">
                              <BarChart3 className="w-3.5 h-3.5" />
                              {feed.posts_per_week}/нед
                            </span>
                            <span className="flex items-center gap-1" title="Последний пост">
                              <Clock className="w-3.5 h-3.5" />
                              {formatRelativeTime(feed.last_post_at)}
                            </span>
                          </div>
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
