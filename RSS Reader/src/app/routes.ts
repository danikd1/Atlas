import { createBrowserRouter } from "react-router";
import { Root } from "./components/Root";
import { HomePage } from "./components/HomePage";
import { FeedsPage } from "./components/FeedsPage";
import { ArticlesPage } from "./components/ArticlesPage";
import { ArticleDetailPage } from "./components/ArticleDetailPage";
import { TodayPage } from "./components/TodayPage";
import { UnreadPage } from "./components/UnreadPage";
import { SavedPage } from "./components/SavedPage";
import { FeedArticlesPage } from "./components/FeedArticlesPage";
import { SourceFeedsPage } from "./components/SourceFeedsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: HomePage },
      { path: "articles", Component: ArticlesPage },
      { path: "feeds", Component: FeedsPage },
      { path: "today", Component: TodayPage },
      { path: "unread", Component: UnreadPage },
      { path: "saved", Component: SavedPage },
      { path: "feed/:feedId", Component: FeedArticlesPage },
      { path: "article/:id", Component: ArticleDetailPage },
      { path: "source/:feedUrl", Component: SourceFeedsPage },
    ],
  },
]);