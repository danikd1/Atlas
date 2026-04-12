import { createBrowserRouter } from "react-router";
import { Root } from "./components/Root";
import { HomePage } from "./components/HomePage";
import { FeedsPage } from "./components/FeedsPage";
import { ArticleDetailPage } from "./components/ArticleDetailPage";
import { SourceFeedsPage } from "./components/SourceFeedsPage";
import { TopicMapPage } from "./components/TopicMapPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: HomePage },
      { path: "feeds", Component: FeedsPage },
      { path: "map", Component: TopicMapPage },
      { path: "article/:id", Component: ArticleDetailPage },
      { path: "source/:feedUrl", Component: SourceFeedsPage },
    ],
  },
]);
