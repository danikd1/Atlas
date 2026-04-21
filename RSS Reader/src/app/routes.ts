import { createBrowserRouter } from "react-router";
import { Root } from "./components/Root";
import { HomePage } from "./components/HomePage";
import { FeedsPage } from "./components/FeedsPage";
import { ArticleDetailPage } from "./components/ArticleDetailPage";
import { SourceFeedsPage } from "./components/SourceFeedsPage";
import { SourceHubPage } from "./components/SourceHubPage";
import { TopicMapPage } from "./components/TopicMapPage";
import { LoginPage } from "./components/LoginPage";
import { RegisterPage } from "./components/RegisterPage";

export const router = createBrowserRouter([
  { path: "login", Component: LoginPage },
  { path: "register", Component: RegisterPage },
  {
    path: "/",
    Component: Root,
    children: [
      { index: true, Component: HomePage },
      { path: "feeds", Component: FeedsPage },
      { path: "map", Component: TopicMapPage },
      { path: "article/:id", Component: ArticleDetailPage },
      { path: "source/:feedUrl", Component: SourceFeedsPage },
      { path: "source-hub/:feedUrl", Component: SourceHubPage },
    ],
  },
]);
