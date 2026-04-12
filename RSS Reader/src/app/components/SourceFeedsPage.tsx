import { useState, useEffect } from "react";
import { useParams, useNavigate, useOutletContext } from "react-router";
import { ArrowLeft, Rss, TrendingUp, Users, BarChart3, Clock, Loader2 } from "lucide-react";
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
        className="w-5 h-5 rounded"
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    );
  }
  if (category?.toLowerCase().includes("engineering") || category?.toLowerCase().includes("tech")) {
    return <TrendingUp className="w-5 h-5" />;
  }
  return <Rss className="w-5 h-5" />;
}

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

export function SourceFeedsPage() {
  const { feedUrl } = useParams<{ feedUrl: string }>();
  const navigate = useNavigate();
  const context = useOutletContext<OutletCtx | undefined>();
  const setSelectedSource = context?.setSelectedSource;
  const activeKey = sourceKey(context?.selectedSource ?? null);

  const [feeds, setFeeds] = useState<ApiCatalogFeed[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const domain = feedUrl ? decodeURIComponent(feedUrl) : "";

  useEffect(() => {
    loadFeeds();
  }, [domain]);

  const loadFeeds = async () => {
    setIsLoading(true);
    try {
      const catalog = await api.getCatalog();
      const domainFeeds = catalog.filter((f) => getDomain(f.url) === domain);
      setFeeds(domainFeeds);
    } catch (e) {
      console.error("Ошибка загрузки лент:", e);
    } finally {
      setIsLoading(false);
    }
  };

  const silentReloadFeeds = async () => {
    try {
      const catalog = await api.getCatalog();
      const domainFeeds = catalog.filter((f) => getDomain(f.url) === domain);
      setFeeds(domainFeeds);
    } catch (e) {
      console.error("Ошибка обновления лент:", e);
    }
  };

  const handleSubscribe = async (feed: ApiCatalogFeed) => {
    try {
      await api.addFeed({
        url: feed.url,
        name: feed.name,
        favicon_url: feed.favicon_url,
        description: feed.description,
        category: feed.category,
      });
      setFeeds((prev) => prev.map((f) => f.id === feed.id ? { ...f, is_subscribed: true } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReloadFeeds, 1500);
    } catch (e) {
      console.error("Ошибка при подписке:", e);
    }
  };

  const handleUnsubscribe = async (feed: ApiCatalogFeed) => {
    try {
      await api.deleteFeed(feed.id);
      setFeeds((prev) => prev.map((f) => f.id === feed.id ? { ...f, is_subscribed: false } : f));
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      setTimeout(silentReloadFeeds, 1500);
    } catch (e) {
      console.error("Ошибка при отписке:", e);
    }
  };

  const sourceName = feeds.length > 0 ? getDomain(feeds[0].url) : domain;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={(e) => { e.stopPropagation(); navigate("/"); }}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Назад к источникам</span>
        </button>

        <h1 className="text-3xl font-bold text-gray-900 mb-1">{sourceName}</h1>
        {feeds.length > 0 && (
          <p className="text-gray-500 text-sm">
            {feeds.length} {feeds.length === 1 ? "лента" : feeds.length < 5 ? "ленты" : "лент"} •{" "}
            {feeds.filter((f) => f.is_subscribed).length} подписок
          </p>
        )}
      </div>

      {/* Feed List */}
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {feeds.map((feed) => {
            const isActive = activeKey === `feed:${feed.id.toString()}`;
            return (
            <div
              key={feed.id}
              onClick={(e) => {
                e.stopPropagation();
                setSelectedSource?.({
                  kind: "feed",
                  feedId: feed.id.toString(),
                  title: feed.name,
                  favicon_url: feed.favicon_url ?? undefined,
                });
              }}
              className={`bg-white rounded-lg shadow-sm border-2 p-5 hover:shadow-md transition-all cursor-pointer ${
                isActive
                  ? "border-blue-500 ring-2 ring-blue-200"
                  : feed.is_subscribed
                  ? "border-blue-200 bg-blue-50/20"
                  : "border-gray-200"
              }`}
            >
              <div className="flex items-start gap-4 mb-4">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    feed.is_subscribed ? "bg-blue-100" : "bg-gray-100"
                  }`}
                >
                  <FeedIcon faviconUrl={feed.favicon_url} category={feed.category} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h3 className="font-medium text-gray-900">{feed.name}</h3>
                    {feed.category && (
                      <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded whitespace-nowrap flex-shrink-0">
                        {feed.category}
                      </span>
                    )}
                  </div>
                  {feed.description && (
                    <p className="text-sm text-gray-600">{feed.description}</p>
                  )}
                </div>
              </div>

              {/* Statistics */}
              <div className="flex items-center gap-4 mb-4 text-xs text-gray-500">
                <div className="flex items-center gap-1" title="Подписчики">
                  <Users className="w-3.5 h-3.5" />
                  <span>{formatSubscribers(feed.subscribers)}</span>
                </div>
                <div className="flex items-center gap-1" title="Постов в день">
                  <BarChart3 className="w-3.5 h-3.5" />
                  <span>{feed.posts_per_week}/нед</span>
                </div>
                <div className="flex items-center gap-1" title="Последний пост">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{formatRelativeTime(feed.last_post_at)}</span>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  feed.is_subscribed ? handleUnsubscribe(feed) : handleSubscribe(feed);
                }}
                className={`text-sm px-4 py-1.5 rounded-md transition-colors ${
                  feed.is_subscribed
                    ? "bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600"
                    : "bg-blue-600 text-white hover:bg-blue-700"
                }`}
              >
                {feed.is_subscribed ? "Отписаться" : "Подписаться"}
              </button>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
