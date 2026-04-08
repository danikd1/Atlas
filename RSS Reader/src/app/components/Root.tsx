import { Outlet, Link, useLocation } from "react-router";
import { Newspaper, Rss, Home } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ArticlesSidebar } from "./ArticlesSidebar";
import { useState } from "react";
import { RSSFeed } from "../types";

export function Root() {
  const location = useLocation();
  const [selectedFeed, setSelectedFeed] = useState<RSSFeed | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
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

      <div className="flex">
        <Sidebar />
        {selectedFeed && (
          <ArticlesSidebar 
            feed={selectedFeed} 
            onClose={() => setSelectedFeed(null)} 
          />
        )}
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-8">
          <Outlet context={{ setSelectedFeed }} />
        </main>
      </div>
    </div>
  );
}