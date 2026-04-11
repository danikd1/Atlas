import { createBrowserRouter } from "react-router";
import { Root } from "./components/Root";
import { HomePage } from "./components/HomePage";
import { FeedsPage } from "./components/FeedsPage";
import { ArticleDetailPage } from "./components/ArticleDetailPage";
import { SourceFeedsPage } from "./components/SourceFeedsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: HomePage },
      { path: "feeds", Component: FeedsPage },
      { path: "article/:id", Component: ArticleDetailPage },
      { path: "source/:feedUrl", Component: SourceFeedsPage },
    ],
  },
]);
