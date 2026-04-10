import { Outlet, Link, useLocation } from "react-router";
import { Newspaper, Rss, Home } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ArticlesSidebar } from "./ArticlesSidebar";
import { useState, useEffect } from "react";
import { RSSFeed } from "../types";

export function Root() {
  const location = useLocation();
  const [selectedFeed, setSelectedFeed] = useState<RSSFeed | null>(null);

  const [sidebarWidth, setSidebarWidth] = useState(() =>
    parseInt(localStorage.getItem("sidebarWidth") || "256")
  );
  const [articlesSidebarWidth, setArticlesSidebarWidth] = useState(() =>
    parseInt(localStorage.getItem("articlesSidebarWidth") || "320")
  );

  useEffect(() => {
    localStorage.setItem("sidebarWidth", String(sidebarWidth));
  }, [sidebarWidth]);

  useEffect(() => {
    localStorage.setItem("articlesSidebarWidth", String(articlesSidebarWidth));
  }, [articlesSidebarWidth]);

  const toggleSelectedFeed = (feed: RSSFeed | null) => {
    if (feed && selectedFeed && feed.id === selectedFeed.id) {
      setSelectedFeed(null);
    } else {
      setSelectedFeed(feed);
    }
  };

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
            <Link to="/" className="flex items-center gap-2">
              <Newspaper className="w-8 h-8 text-blue-600" />
              <h1 className="text-xl font-semibold text-gray-900">RSS Reader</h1>
            </Link>

            <nav className="flex gap-1">
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
            </nav>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Левый сайдбар + drag handle */}
        <div className="relative flex-shrink-0 flex" style={{ width: sidebarWidth }}>
          <Sidebar />
          <div
            onMouseDown={makeResizeHandler(setSidebarWidth, sidebarWidth, 180, 480)}
            className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors z-20"
          />
        </div>

        {/* Панель статей + drag handle */}
        {selectedFeed && (
          <div className="relative flex-shrink-0 flex" style={{ width: articlesSidebarWidth }}>
            <ArticlesSidebar
              feed={selectedFeed}
              onClose={() => setSelectedFeed(null)}
            />
            <div
              onMouseDown={makeResizeHandler(setArticlesSidebarWidth, articlesSidebarWidth, 220, 600)}
              className="absolute right-0 top-0 h-full w-1 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors z-20"
            />
          </div>
        )}

        <main
          className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-8"
          onClick={() => { if (selectedFeed) setSelectedFeed(null); }}
        >
          <Outlet context={{ setSelectedFeed: toggleSelectedFeed, selectedFeed }} />
        </main>
      </div>
    </div>
  );
}