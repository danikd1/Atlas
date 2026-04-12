import { useState, useEffect } from "react";
import { useNavigate, useOutletContext } from "react-router";
import { Rss, TrendingUp, Newspaper, Search, Users, BarChart3, Clock, Layers, Eye, Loader2, ArrowRight } from "lucide-react";
import { api, ApiCatalogFeed, ApiFeed } from "../lib/api";
import { OutletCtx, sourceKey } from "../types";

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function formatSourceName(domain: string): string {
  const stripped = domain.replace(/^www\./, "");
  const parts = stripped.split(".");
  if (parts.length <= 2) {
    return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
  }
  return parts.slice(0, -1).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

function commonNamePrefix(names: string[]): string | null {
  if (names.length === 0) return null;
  const words = names[0].split(" ");
  const prefix: string[] = [];
  for (const word of words) {
    const candidate = [...prefix, word].join(" ").toLowerCase();
    if (names.every((n) => n.toLowerCase().startsWith(candidate))) {
      prefix.push(word);
    } else break;
  }
  return prefix.length > 0 ? prefix.join(" ") : null;
}

function FeedIcon({ faviconUrl, category }: { faviconUrl: string | null; category: string | null }) {
  if (faviconUrl) {
    return <img src={faviconUrl} alt="" className="w-5 h-5 rounded" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />;
  }
  if (category?.toLowerCase().includes("engineering") || category?.toLowerCase().includes("tech")) {
    return <TrendingUp className="w-5 h-5" />;
  }
  return <Rss className="w-5 h-5" />;
}

export function HomePage() {
  const navigate = useNavigate();
  const context = useOutletContext<OutletCtx | undefined>();
  const setSelectedSource = context?.setSelectedSource;
  const selectedSource = context?.selectedSource ?? null;
  const activeKey = sourceKey(selectedSource);

  const [catalog, setCatalog] = useState<ApiCatalogFeed[]>([]);
  const [hiddenFeeds, setHiddenFeeds] = useState<ApiFeed[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategories, setActiveCategories] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadCatalog();
    loadHiddenFeeds();
  }, []);

  const loadCatalog = async () => {
    setIsLoading(true);
    try {
      const data = await api.getCatalog();
      setCatalog(data);
      setActiveCategories((prev) => {
        if (prev.size === 0) {
          return new Set(data.map((f) => f.category ?? "Other"));
        }
        return prev;
      });
    } catch (e) {
      console.error("Ошибка загрузки каталога:", e);
    } finally {
      setIsLoading(false);
    }
  };

  // Тихое обновление каталога — без setIsLoading, скролл не сбрасывается
  const silentReloadCatalog = async () => {
    try {
      const data = await api.getCatalog();
      setCatalog(data);
    } catch (e) {
      console.error("Ошибка обновления каталога:", e);
    }
  };

  const loadHiddenFeeds = async () => {
    try {
      const feeds = await api.getFeeds(true);
      setHiddenFeeds(feeds.filter((f) => f.hidden));
    } catch (e) {
      console.error("Ошибка загрузки скрытых лент:", e);
    }
  };

  const handleSubscribe = async (feeds: ApiCatalogFeed[], sourceName: string) => {
    try {
      if (feeds.length > 1) {
        const folder = await api.createFolder(sourceName, feeds[0].favicon_url);
        await Promise.all(
          feeds.map((f) =>
            api.addFeed({ url: f.url, name: f.name, favicon_url: f.favicon_url, description: f.description, category: f.category, folder_id: folder.id })
          )
        );
      } else {
        await api.addFeed({ url: feeds[0].url, name: feeds[0].name, favicon_url: feeds[0].favicon_url, description: feeds[0].description, category: feeds[0].category });
      }
      const subscribedIds = new Set(feeds.map((f) => f.id));
      setCatalog((prev) => prev.map((f) => subscribedIds.has(f.id) ? { ...f, is_subscribed: true } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReloadCatalog, 1500);
    } catch (e) {
      console.error("Ошибка при подписке:", e);
    }
  };

  const handleUnsubscribe = async (feed: ApiCatalogFeed) => {
    const domain = getDomain(feed.url);
    const sameDomainSubscribed = catalog.filter((f) => getDomain(f.url) === domain && f.is_subscribed);
    try {
      const myFeeds = await api.getFeeds(true);
      const folderIds = new Set(
        myFeeds
          .filter((f) => sameDomainSubscribed.some((s) => s.id === f.id) && f.folder_id != null)
          .map((f) => f.folder_id as number)
      );
      await Promise.all(sameDomainSubscribed.map((f) => api.deleteFeed(f.id)));
      await Promise.all([...folderIds].map((fid) => api.deleteFolder(fid)));
      const unsubscribedIds = new Set(sameDomainSubscribed.map((f) => f.id));
      setCatalog((prev) => prev.map((f) => unsubscribedIds.has(f.id) ? { ...f, is_subscribed: false } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      await loadHiddenFeeds();
      setTimeout(silentReloadCatalog, 1500);
    } catch (e) {
      console.error("Ошибка при отписке:", e);
    }
  };

  const handleUnhideFeed = async (feed: ApiFeed) => {
    try {
      await api.patchFeed(feed.id, { hidden: false });
      await loadHiddenFeeds();
    } catch (e) {
      console.error("Ошибка:", e);
    }
  };

  const handleCardClick = (e: React.MouseEvent, representative: ApiCatalogFeed, allFeeds: ApiCatalogFeed[], sourceName: string) => {
    e.stopPropagation();
    if (!setSelectedSource) return;
    setSelectedSource({
      kind: "feed",
      feedId: representative.id.toString(),
      feedIds: allFeeds.map((f) => f.id),
      title: sourceName,
      favicon_url: representative.favicon_url ?? undefined,
    });
  };

  const formatSubscribers = (count: number): string => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(0)}K`;
    return count.toString();
  };

  const formatRelativeTime = (dateString: string | null): string => {
    if (!dateString) return "нет данных";
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
    if (diffInHours < 1) {
      return `${Math.floor((now.getTime() - date.getTime()) / (1000 * 60))} мин назад`;
    } else if (diffInHours < 24) {
      return `${diffInHours} ч назад`;
    } else {
      return `${Math.floor(diffInHours / 24)} дн назад`;
    }
  };

  const toggleCategory = (category: string) => {
    setActiveCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  // Группировка каталога по домену
  const feedsByDomain = new Map<string, ApiCatalogFeed[]>();
  catalog.forEach((f) => {
    const d = getDomain(f.url);
    if (!feedsByDomain.has(d)) feedsByDomain.set(d, []);
    feedsByDomain.get(d)!.push(f);
  });

  // Одна карточка на домен
  const displayGroups = Array.from(feedsByDomain.entries()).map(([domain, feeds]) => {
    const latestPostAt = feeds.reduce<string | null>((latest, f) => {
      if (!f.last_post_at) return latest;
      if (!latest) return f.last_post_at;
      return new Date(f.last_post_at) > new Date(latest) ? f.last_post_at : latest;
    }, null);
    return {
      domain,
      feeds,
      representative: feeds[0],
      sourceName: feeds.length > 1
        ? (commonNamePrefix(feeds.map((f) => f.name)) ?? formatSourceName(domain))
        : feeds[0].name,
      latestPostAt,
      isSubscribed: feeds.some((f) => f.is_subscribed),
      categories: Array.from(new Set(feeds.map((f) => f.category ?? "Other"))),
    };
  });

  const allCategories = Array.from(new Set(catalog.map((f) => f.category ?? "Other")));

  const filteredGroups = displayGroups.filter(({ representative, categories }) => {
    if (!categories.some((c) => activeCategories.has(c))) return false;
    const q = searchQuery.toLowerCase();
    return (
      representative.name.toLowerCase().includes(q) ||
      (representative.description ?? "").toLowerCase().includes(q) ||
      categories.some((c) => c.toLowerCase().includes(q))
    );
  });

  const subscribedCount = new Set(
    catalog.filter((f) => f.is_subscribed).map((f) => getDomain(f.url))
  ).size;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
          <Rss className="w-8 h-8 text-blue-600" />
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-3">Мои Источники</h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Управляйте подписками и добавляйте новые RSS-ленты
        </p>
      </div>

      {/* Quick Actions */}
      {subscribedCount > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Newspaper className="w-5 h-5 text-blue-600" />
            <span className="text-sm text-blue-900">
              У вас {subscribedCount} {subscribedCount === 1 ? "подписка" : "подписки"}
            </span>
          </div>
          <button
            onClick={() => navigate("/feeds")}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
          >
            Управление источниками →
          </button>
        </div>
      )}

      {/* Catalog */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Популярные источники</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Поиск..."
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Category Filter */}
        {allCategories.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-gray-600 font-medium">Категории:</span>
              {allCategories.map((category) => {
                const isActive = activeCategories.has(category);
                const count = displayGroups.filter((g) => g.categories.includes(category)).length;
                return (
                  <button
                    key={category}
                    onClick={() => toggleCategory(category)}
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                      isActive
                        ? "bg-blue-600 text-white shadow-sm hover:bg-blue-700"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    <span>{category}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${isActive ? "bg-blue-500" : "bg-gray-200"}`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
            {activeCategories.size === 0 && (
              <p className="text-sm text-amber-600 mt-2 flex items-center gap-1">
                <span>⚠️</span>
                <span>Выберите хотя бы одну категорию для отображения источников</span>
              </p>
            )}
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-gray-400">
            <Loader2 className="w-8 h-8 animate-spin mr-3" />
            Загрузка каталога...
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredGroups.map(({ domain, feeds, representative, sourceName, latestPostAt, isSubscribed, categories }) => {
              const hasMultiple = feeds.length > 1;
              const isActive = activeKey === `feed:${representative.id.toString()}`;
              return (
                <div
                  key={domain}
                  className={`bg-white rounded-lg shadow-sm border-2 p-5 hover:shadow-md transition-all relative cursor-pointer flex flex-col ${
                    isActive
                      ? "border-blue-500 ring-2 ring-blue-200"
                      : hasMultiple
                      ? "border-blue-300 bg-gradient-to-br from-blue-50/30 to-white"
                      : "border-gray-200"
                  }`}
                  onClick={(e) => handleCardClick(e, representative, feeds, sourceName)}
                >
                  {hasMultiple ? (
                    <div className="flex gap-3 mb-3">
                      {/* Left: logo + name + description */}
                      <div className="w-1/2 min-w-0 flex gap-3">
                        <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 bg-blue-100">
                          <FeedIcon faviconUrl={representative.favicon_url} category={representative.category} />
                        </div>
                        <div className="flex flex-col gap-1 min-w-0">
                          <h3 className="font-medium text-gray-900">{sourceName}</h3>
                          {(representative.source_description || representative.description) && (
                            <p className="text-sm text-gray-600">
                              {representative.source_description || representative.description}
                            </p>
                          )}
                        </div>
                      </div>
                      {/* Right: badge + categories */}
                      <div className="w-1/2 flex flex-col items-end gap-2">
                        <div className="bg-blue-600 text-white px-2 py-0.5 rounded-full flex items-center gap-1 text-xs font-medium">
                          <Layers className="w-3 h-3" />
                          <span>{feeds.length} {feeds.length < 5 ? "ленты" : "лент"}</span>
                        </div>
                        <div className="flex flex-wrap justify-end gap-1">
                          {categories.map((cat) => (
                            <span key={cat} className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded whitespace-nowrap">
                              {cat}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-4 mb-3">
                      <div className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 bg-gray-100">
                        <FeedIcon faviconUrl={representative.favicon_url} category={representative.category} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <h3 className="font-medium text-gray-900">{sourceName}</h3>
                          {categories[0] && (
                            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded whitespace-nowrap flex-shrink-0">
                              {categories[0]}
                            </span>
                          )}
                        </div>
                        {(representative.source_description || representative.description) && (
                          <p className="text-sm text-gray-600 mb-1">
                            {representative.source_description || representative.description}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Statistics */}
                  <div className="flex items-center gap-4 mb-2 mt-auto text-xs text-gray-500">
                    <div className="flex items-center gap-1" title="Подписчики">
                      <Users className="w-3.5 h-3.5" />
                      <span>{(() => {
                        const vals = feeds.map((f) => f.subscribers);
                        const mn = Math.min(...vals);
                        const mx = Math.max(...vals);
                        return mn === mx ? formatSubscribers(mx) : `${formatSubscribers(mn)}–${formatSubscribers(mx)}`;
                      })()}</span>
                    </div>
                    <div className="flex items-center gap-1" title="Постов в неделю">
                      <BarChart3 className="w-3.5 h-3.5" />
                      <span>{feeds.reduce((sum, f) => sum + f.posts_per_week, 0)}/нед</span>
                    </div>
                    <div className="flex items-center gap-1" title="Последний пост">
                      <Clock className="w-3.5 h-3.5" />
                      <span>{formatRelativeTime(latestPostAt)}</span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-between gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        isSubscribed ? handleUnsubscribe(representative) : handleSubscribe(feeds, sourceName);
                      }}
                      className={`text-sm px-4 py-1.5 rounded-md transition-colors ${
                        isSubscribed
                          ? "bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600"
                          : "bg-blue-600 text-white hover:bg-blue-700"
                      }`}
                    >
                      {isSubscribed ? "Отписаться" : "Подписаться"}
                    </button>
                    {hasMultiple && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/source/${encodeURIComponent(domain)}`);
                        }}
                        className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 transition-colors"
                      >
                        Управление <ArrowRight className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!isLoading && filteredGroups.length === 0 && (
          <div className="text-center py-12 text-gray-500">Источники не найдены</div>
        )}
      </div>

      {/* Hidden Feeds Section */}
      {hiddenFeeds.length > 0 && (
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Скрытые источники ({hiddenFeeds.length})
          </h2>
          <div className="space-y-2">
            {hiddenFeeds.map((feed) => (
              <div
                key={feed.id}
                className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  {feed.favicon_url ? (
                    <img src={feed.favicon_url} alt="" className="w-4 h-4 rounded" />
                  ) : (
                    <Rss className="w-4 h-4 text-gray-400" />
                  )}
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">{feed.name}</h3>
                    {feed.description && (
                      <p className="text-xs text-gray-500">{feed.description}</p>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleUnhideFeed(feed)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  Показать
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
