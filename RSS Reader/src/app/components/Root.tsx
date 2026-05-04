import { Outlet, Link, useLocation, useNavigate, Navigate } from "react-router";
import { Rss, Home, Search, X, Map, LogOut, User, Play, Pause, Database } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ArticlesSidebar } from "./ArticlesSidebar";
import { ProfileModal } from "./ProfileModal";
import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { ArticleSource, OutletCtx } from "../types";
import { api, ApiArticleItem } from "../lib/api";
import { authService } from "../lib/authService";
import atlasLogo from "../assets/atlas-logo2.png";

export function Root() {
  // ── Auth guard ────────────────────────────────────────────────
  if (!authService.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
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

  const [showProfile, setShowProfile] = useState(false);

  // ── RAG index bar ─────────────────────────────────────────────
  const [ragStatus, setRagStatus] = useState<{
    rag_indexed: number;
    rag_pending: number;
    rag_indexing: boolean;
    rag_paused: boolean;
    text_extraction_pending: number;
    text_extraction_running: boolean;
  } | null>(null);
  const [ragTooltip, setRagTooltip] = useState(false);
  const [ragTooltipPos, setRagTooltipPos] = useState<{ left: number; top: number } | null>(null);
  const ragBarRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLElement>(null);

  const fetchRagStatus = useCallback(async () => {
    try {
      const s = await api.getRssStatus();
      setRagStatus({
        rag_indexed: s.rag_indexed,
        rag_pending: s.rag_pending,
        rag_indexing: s.rag_indexing,
        rag_paused: s.rag_paused,
        text_extraction_pending: s.text_extraction_pending,
        text_extraction_running: s.text_extraction_running,
      });
    } catch {}
  }, []);

  useEffect(() => {
    fetchRagStatus();
    // Активно (5 сек) когда что-то происходит, редко (30 сек) в простое
    const isActive = ragStatus?.rag_indexing || ragStatus?.text_extraction_running;
    const id = setInterval(fetchRagStatus, isActive ? 5_000 : 30_000);
    return () => clearInterval(id);
  }, [fetchRagStatus, ragStatus?.rag_indexing, ragStatus?.text_extraction_running]);

  // Обновляем RAG-статус сразу при подписке/отписке
  useEffect(() => {
    window.addEventListener("feeds-updated", fetchRagStatus);
    return () => window.removeEventListener("feeds-updated", fetchRagStatus);
  }, [fetchRagStatus]);

  const handleRagPauseResume = async () => {
    try {
      if (ragStatus?.rag_paused) {
        await api.resumeRagIndexer();
      } else {
        await api.pauseRagIndexer();
      }
      await fetchRagStatus();
    } catch {}
  };

  const handleRagStart = async () => {
    try {
      if (ragStatus && ragStatus.text_extraction_pending > 0) {
        await api.startExtractionWorker();
      } else {
        await api.startRagIndexer();
      }
      await fetchRagStatus();
    } catch {}
  };

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
      {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
      <header ref={headerRef} className="relative bg-white border-b border-gray-200 z-50 flex-shrink-0">
        <div className="px-4 sm:px-6 lg:px-8 h-16 flex items-center gap-4">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 flex-shrink-0">
            <img src={atlasLogo} alt="Atlas" className="w-10 h-10 object-contain" />
            <span
              className="text-xl font-black tracking-widest uppercase text-gray-900"
              style={{ fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif", letterSpacing: "0.18em" }}
            >
              Atlas
            </span>
          </Link>

          {/* Nav */}
          <nav className="flex gap-1 flex-shrink-0">
            <Link
              to="/"
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                location.pathname === "/" ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <Home className="w-4 h-4" />
              Главная
            </Link>
            <Link
              to="/feeds"
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                location.pathname === "/feeds" ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <Rss className="w-4 h-4" />
              Мои Источники
            </Link>
            <Link
              to="/map"
              className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                location.pathname === "/map" ? "bg-blue-100 text-blue-700" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <Map className="w-4 h-4" />
              Карта
            </Link>
          </nav>

          {/* Search — flex-1, оригинальное положение по центру */}
          <div ref={searchRef} className="relative flex-1 mx-4">
            <div className="relative max-w-md mx-auto">
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
            {searchOpen && (
              <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 w-[520px] bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-h-[480px] overflow-y-auto">
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

          {/* База знаний (RAG) + Профиль + Выйти */}
          <div className="flex items-center gap-3 flex-shrink-0">

            {/* RAG progress bar */}
            {ragStatus && (ragStatus.rag_indexed > 0 || ragStatus.rag_pending > 0) && (() => {
              const { rag_indexed: indexed, rag_pending: pending, rag_indexing: isIndexing, rag_paused: isPaused, text_extraction_pending: extractPending, text_extraction_running: extractRunning } = ragStatus;
              const total = indexed + pending;
              const pct = total > 0 ? (pending === 0 ? 100 : Math.min(Math.floor((indexed / total) * 100), 99)) : 100;
              return (
                <div className="flex items-center gap-1.5 border-r border-gray-200 pr-3">
                  <div
                    ref={ragBarRef}
                    className="cursor-default"
                    onMouseEnter={() => {
                      if (headerRef.current) {
                        const hr = headerRef.current.getBoundingClientRect();
                        const br = ragBarRef.current!.getBoundingClientRect();
                        setRagTooltipPos({ left: Math.max(br.right - 288, 8), top: hr.bottom + 8 });
                      }
                      setRagTooltip(true);
                    }}
                    onMouseLeave={() => { setRagTooltip(false); setRagTooltipPos(null); }}
                  >
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs text-gray-400 leading-none whitespace-nowrap">
                        {isIndexing && !isPaused ? "База знаний..." :
                         isPaused ? "База знаний: пауза" :
                         pending === 0 ? `База знаний: ${indexed}` :
                         `База знаний: ${indexed} / ${total}`}
                      </span>
                      <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${isPaused ? "bg-gray-300" : "bg-blue-400"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {!isIndexing && !extractRunning && pending > 0 && (
                    <div className="relative group">
                      <button
                        type="button"
                        onClick={handleRagStart}
                        className="p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                      >
                        <Play className="w-3.5 h-3.5" />
                      </button>
                      <div className="pointer-events-none absolute top-full right-0 mt-2 hidden group-hover:block z-50">
                        <div className="bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
                          {extractPending > 0 ? "Извлечь тексты и проиндексировать" : "Запустить индексацию"}
                        </div>
                        <div className="absolute bottom-full right-2.5 border-4 border-transparent border-b-gray-800" />
                      </div>
                    </div>
                  )}
                  {isIndexing && (
                    <button
                      type="button"
                      onClick={handleRagPauseResume}
                      title={isPaused ? "Возобновить" : "Пауза"}
                      className="p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                    >
                      {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                    </button>
                  )}

                  {ragTooltip && ragTooltipPos && createPortal(
                    <div
                      style={{ position: "fixed", left: ragTooltipPos.left, top: ragTooltipPos.top, zIndex: 2147483647 }}
                      className="w-72 bg-gray-900 text-white text-xs rounded-lg px-3 py-2.5 shadow-xl leading-relaxed pointer-events-none"
                    >
                      <div className="flex items-center gap-1.5 mb-1.5 font-medium">
                        <Database className="w-3.5 h-3.5 flex-shrink-0" />
                        Что такое База знаний?
                      </div>
                      <p className="text-gray-300">
                        Чтобы отвечать на вопросы точно, Atlas разбивает статьи на фрагменты и сохраняет их в векторную базу данных.
                      </p>
                      <p className="text-gray-300 mt-1.5">
                        Пока база строится, вопросы обрабатываются по краткому описанию статей. Как только все статьи проиндексированы — QA переключается на точный поиск по полным текстам.
                      </p>
                      {extractPending > 0 && (
                        <p className="mt-1.5 text-amber-300">
                          ⏳ {extractPending} {extractPending === 1 ? "статья ждёт" : "статей ждут"} извлечения текста
                        </p>
                      )}
                      <p className="mt-1 text-gray-400">
                        {pending === 0
                          ? "✓ База актуальна — QA работает по полным текстам"
                          : `${pct}% готово (${indexed} из ${total})`}
                      </p>
                    </div>,
                    document.body
                  )}
                </div>
              );
            })()}

            <button
              onClick={() => setShowProfile(true)}
              className="px-3 py-2 rounded-md text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors flex items-center gap-1.5"
              title="Профиль"
            >
              <User className="w-4 h-4" />
              <span className="hidden sm:inline">Профиль</span>
            </button>
            <button
              onClick={() => { authService.logout(); navigate("/login", { replace: true }); }}
              className="px-3 py-2 rounded-md text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors flex items-center gap-1.5"
              title="Выйти"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Выйти</span>
            </button>
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
