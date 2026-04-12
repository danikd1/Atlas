import { Outlet, Link, useLocation, useNavigate } from "react-router";
import { Newspaper, Rss, Home, Search, X, Map } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ArticlesSidebar } from "./ArticlesSidebar";
import { useState, useEffect, useRef, useCallback } from "react";
import { ArticleSource, OutletCtx } from "../types";
import { api, ApiArticleItem } from "../lib/api";

export function Root() {
  const location = useLocation();
  const navigate = useNavigate();
  const [selectedSource, setSelectedSourceState] = useState<ArticleSource | null>(null);

  // ── Search ──────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ApiArticleItem[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < 2) {
      setSearchResults([]);
      setSearchOpen(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const results = await api.searchArticles(value.trim());
        setSearchResults(results);
        setSearchOpen(true);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
  }, []);

  const handleSearchSelect = (article: ApiArticleItem) => {
    if (article.feed_id) {
      setSelectedSourceState({
        kind: "feed",
        feedId: article.feed_id.toString(),
        title: article.source ?? "Лента",
      });
    }
    navigate(`/article/${article.id}`);
    setSearchQuery("");
    setSearchResults([]);
    setSearchOpen(false);
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults([]);
    setSearchOpen(false);
  };

  // Закрытие по клику вне
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const [sidebarWidth, setSidebarWidth] = useState(() =>
    parseInt(localStorage.getItem("sidebarWidth") || "256")
  );
  const [articlesSidebarWidth, setArticlesSidebarWidth] = useState(() =>
    parseInt(localStorage.getItem("articlesSidebarWidth") || "420")
  );

  useEffect(() => {
    localStorage.setItem("sidebarWidth", String(sidebarWidth));
  }, [sidebarWidth]);

  useEffect(() => {
    localStorage.setItem("articlesSidebarWidth", String(articlesSidebarWidth));
  }, [articlesSidebarWidth]);

  const setSelectedSource = (source: ArticleSource | null) => {
    setSelectedSourceState(source);
  };

  const ctx: OutletCtx = { selectedSource, setSelectedSource };

  const makeResizeHandler = (
    setter: (w: number) => void,
    currentWidth: number,
    min: number,
    max: number,
    direction: 1 | -1 = 1
  ) => (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = currentWidth;
    const onMove = (ev: MouseEvent) => {
      const delta = (ev.clientX - startX) * direction;
      setter(Math.max(min, Math.min(max, startWidth + delta)));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-gray-200 z-10 flex-shrink-0">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-2 flex-shrink-0">
              <Newspaper className="w-8 h-8 text-blue-600" />
              <h1 className="text-xl font-semibold text-gray-900">RSS Reader</h1>
            </Link>

            {/* Search */}
            <div ref={searchRef} className="relative flex-1 max-w-md mx-6">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  onFocus={() => searchResults.length > 0 && setSearchOpen(true)}
                  onKeyDown={(e) => e.key === "Escape" && clearSearch()}
                  placeholder="Поиск по статьям..."
                  className="w-full pl-9 pr-8 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-gray-50"
                />
                {searchQuery && (
                  <button onClick={clearSearch} className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-gray-200 rounded">
                    <X className="w-3.5 h-3.5 text-gray-400" />
                  </button>
                )}
              </div>

              {/* Dropdown */}
              {searchOpen && (
                <div className="absolute top-full left-0 mt-1 w-[520px] bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-h-[480px] overflow-y-auto">
                  {searchLoading ? (
                    <div className="px-4 py-3 text-sm text-gray-500">Поиск...</div>
                  ) : searchResults.length === 0 ? (
                    <div className="px-4 py-3 text-sm text-gray-500">Ничего не найдено</div>
                  ) : (
                    <ul>
                      {searchResults.map((article) => (
                        <li key={article.id}>
                          <button
                            onClick={() => handleSearchSelect(article)}
                            className="w-full text-left px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-0"
                          >
                            <div className="flex items-start gap-2">
                              {!article.is_read && (
                                <span className="mt-1.5 w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
                              )}
                              <div className="min-w-0">
                                <p className={`text-sm font-medium leading-snug ${article.is_read ? "text-gray-500" : "text-gray-900"}`}>
                                  {article.title ?? "Без заголовка"}
                                </p>
                                <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-2">
                                  <span>{article.source ?? "Источник неизвестен"}</span>
                                  {article.published_at && (
                                    <span>· {new Date(article.published_at).toLocaleDateString("ru-RU")}</span>
                                  )}
                                </p>
                                {article.summary && (
                                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{article.summary}</p>
                                )}
                              </div>
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <nav className="flex gap-1 flex-shrink-0">
              <Link
                to="/"
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
                  location.pathname === "/"
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Home className="w-4 h-4" />
                Главная
              </Link>
              <Link
                to="/feeds"
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
                  location.pathname === "/feeds"
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Rss className="w-4 h-4" />
                Мои Источники
              </Link>
              <Link
                to="/map"
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
                  location.pathname === "/map"
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <Map className="w-4 h-4" />
                Карта
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Левый сайдбар + drag handle */}
        <div className="relative flex-shrink-0 flex" style={{ width: sidebarWidth }}>
          <Sidebar selectedSource={selectedSource} setSelectedSource={setSelectedSource} />
          <div
            onMouseDown={makeResizeHandler(setSidebarWidth, sidebarWidth, 180, 480)}
            className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors z-20"
          />
        </div>

        {/* Панель статей + drag handle */}
        {selectedSource && (
          <div className="relative flex-shrink-0 flex" style={{ width: articlesSidebarWidth }}>
            <ArticlesSidebar
              source={selectedSource}
              onClose={() => setSelectedSource(null)}
            />
            <div
              onMouseDown={makeResizeHandler(setArticlesSidebarWidth, articlesSidebarWidth, 280, 700)}
              className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors z-20"
            />
          </div>
        )}

        <main
          className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-8"
          onClick={() => selectedSource && setSelectedSource(null)}
        >
          <Outlet context={ctx} />
        </main>
      </div>
    </div>
  );
}
