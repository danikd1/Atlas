export interface RSSFeed {
  id: string;
  title: string;
  url: string;
  description?: string;
  addedAt?: string;          // не возвращается API до добавления created_at (решение 1A)
  folderId?: string;
  sourceId?: string;         // устарело: группировка теперь по домену URL
  sourceName?: string;       // устарело: группировка теперь по домену URL
  hidden?: boolean;
  unread_count?: number;     // из API: количество непрочитанных статей
  favicon_url?: string;      // из API: иконка сайта
  error_count?: number;      // из API: кол-во подряд идущих ошибок при сборе
  last_error?: string;       // из API: текст последней ошибки
  category?: string;         // из API: категория ленты
  feedIds?: number[];        // для мульти-лентных источников: все id лент домена
}

export interface Source {
  id: string;
  name: string; // Название источника (GitHub, Google Cloud и т.д.)
  domain: string; // Домен для группировки (github.com, cloud.google.com)
  description: string;
  iconType: string;
  createdAt: string;
}

export interface Folder {
  id: string;
  name: string;
  createdAt: string;
  sourceId?: string; // ID источника, если это папка-источник (для связи с данными источника)
  isSourceFolder?: boolean; // Признак что это папка создана автоматически для источника
}

export interface RSSArticle {
  id: string;
  feedId: string;
  feedTitle: string;
  title: string;
  link: string;
  description: string;
  content?: string;
  pubDate: string;
  author?: string;
  read: boolean;
  saved?: boolean;
}

// ─── Article source для ArticlesSidebar ─────────────────────────────────────
//
// Определяет откуда подгружаются статьи в среднюю панель при клике на элемент
// в левом сайдбаре. Одна из четырёх "умных папок" либо конкретная лента
// (одиночная или мульти — группа лент домена).

export type ArticleSource =
  | { kind: "today" }
  | { kind: "unread" }
  | { kind: "saved" }
  | { kind: "all" }
  | {
      kind: "feed";
      feedId: string;
      feedIds?: number[]; // для мульти-лентных источников: все id лент
      title: string;
      favicon_url?: string;
    };

export function sourceKey(source: ArticleSource | null): string | null {
  if (!source) return null;
  if (source.kind === "feed") return `feed:${source.feedId}`;
  return source.kind;
}

export interface OutletCtx {
  selectedSource: ArticleSource | null;
  setSelectedSource: (source: ArticleSource | null) => void;
}