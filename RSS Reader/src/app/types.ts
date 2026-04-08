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