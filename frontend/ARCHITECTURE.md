# RSS Reader - Архитектура Frontend

## Описание проекта
RSS-ридер на русском языке с поддержкой подписки на RSS-ленты, организации по папкам, drag & drop и различными режимами просмотра статей.

## Технологический стек
- **React 18** + TypeScript
- **React Router** - маршрутизация
- **react-dnd** - drag & drop функциональность
- **Lucide React** - иконки
- **Tailwind CSS** - стилизация
- **localStorage** - хранение данных (требует замены на backend)

## Структура данных

### Types (src/app/types.ts)
```typescript
interface Feed {
  id: string;
  title: string;
  url: string;
  description?: string;
  folderId?: string;
  createdAt: string;
}

interface Article {
  id: string;
  feedId: string;
  title: string;
  content: string;
  link: string;
  pubDate: string;
  author?: string;
  isRead: boolean;
  isSaved: boolean;
}

interface Folder {
  id: string;
  name: string;
  createdAt: string;
  sourceId?: string; // ID источника, если это папка-источник
  isSourceFolder?: boolean; // Папка создана автоматически для источника
}

interface Source {
  id: string;
  name: string;
  description: string;
  icon: string;
  feeds: Array<{
    title: string;
    url: string;
    description?: string;
  }>;
}
```

## Хранение данных (localStorage)

### Текущая реализация (src/app/lib/storage.ts)

**Ключи localStorage:**
- `rss_feeds` - массив Feed[]
- `rss_articles` - массив Article[]
- `rss_folders` - массив Folder[]

**Основные функции:**
- `getFeeds()`, `saveFeeds(feeds)`, `addFeed(feed)`, `removeFeed(id)`, `updateFeed(id, updates)`
- `getArticles()`, `saveArticles(articles)`, `addArticle(article)`, `updateArticle(id, updates)`
- `getFolders()`, `saveFolders(folders)`, `addFolder(name, sourceId?)`, `removeFolder(id)`, `updateFolderName(id, newName)`

### Требования к Backend API

Backend должен предоставить REST API или GraphQL эндпоинты для замены всех функций из `storage.ts`:

**Feeds:**
- `GET /api/feeds` - получить все ленты
- `POST /api/feeds` - добавить ленту
- `PUT /api/feeds/:id` - обновить ленту
- `DELETE /api/feeds/:id` - удалить ленту

**Articles:**
- `GET /api/articles` - получить все статьи (с фильтрами: feedId, isRead, isSaved, date)
- `POST /api/articles` - добавить статью
- `PUT /api/articles/:id` - обновить статью
- `DELETE /api/articles/:id` - удалить статью

**Folders:**
- `GET /api/folders` - получить все папки
- `POST /api/folders` - добавить папку
- `PUT /api/folders/:id` - обновить папку (переименование)
- `DELETE /api/folders/:id` - удалить папку

**RSS Parsing:**
- `POST /api/parse-feed` - парсинг RSS по URL (возвращает Feed метаданные)
- `POST /api/fetch-articles` - получение статей из RSS-ленты

## Архитектура компонентов

### Маршрутизация (src/app/routes.ts)
```
/ (Root)
  ├── / (HomePage) - главная страница с каталогом источников
  ├── /articles (ArticlesPage) - все посты
  ├── /feeds (FeedsPage) - управление подписками
  ├── /today (TodayPage) - статьи за сегодня
  ├── /unread (UnreadPage) - непрочитанные статьи
  ├── /saved (SavedPage) - сохраненные статьи
  ├── /feed/:feedId (FeedArticlesPage) - статьи конкретной ленты
  ├── /article/:id (ArticleDetailPage) - детальный просмотр статьи
  └── /source/:feedUrl (SourceFeedsPage) - предпросмотр ленты перед подпиской
```

### Ключевые компоненты

**Root.tsx** - корневой компонент с навигацией
- Верхняя навигация: "Главная", "Мои Источники"
- Sidebar с фильтрами и списком лент
- Outlet для дочерних страниц

**Sidebar.tsx** - боковое меню
- Системные фильтры: "Все посты", "Сегодня", "Непрочитанное", "Сохраненное"
- Раздел "Источники" с папками и лентами
- Drag & drop для перемещения лент в папки
- Контекстное меню для переименования/удаления папок и лент

**HomePage.tsx** - каталог источников
- Отображение предустановленных источников (src/app/data/sources.ts)
- Подписка на отдельные ленты или на источник целиком
- При подписке на источник автоматически создается папка

**ArticlesPage.tsx** - список всех статей
- Фильтрация по прочитанным/непрочитанным
- Отметка как прочитанное/сохраненное
- Переход к детальному просмотру

**FeedArticlesPage.tsx** - статьи конкретной ленты

**ArticleDetailPage.tsx** - детальный просмотр статьи
- Полное содержимое статьи
- Кнопки: прочитано, сохранено, открыть оригинал

## Ключевые сценарии

### 1. Подписка на ленту
1. Пользователь на главной странице выбирает источник
2. Просматривает доступные ленты в источнике
3. Нажимает "Подписаться"
4. Создается папка с названием источника
5. Все ленты источника добавляются в эту папку
6. В sidebar появляется новая папка с лентами

### 2. Организация лент
1. Пользователь создает папку в sidebar
2. Перетаскивает ленты в папку (drag & drop)
3. Может переименовать папку через контекстное меню (три точки)
4. Может удалить папку (ленты остаются в корне)

### 3. Чтение статей
1. Пользователь выбирает фильтр или ленту в sidebar
2. Видит список статей
3. Кликает на статью для детального просмотра
4. Отмечает как прочитанное/сохраненное
5. Может открыть оригинал в новой вкладке

## Что нужно для backend интеграции

1. **Заменить localStorage на API calls** в `src/app/lib/storage.ts`
2. **Добавить RSS парсинг** на backend (Node.js библиотеки: `rss-parser`, `feed`)
3. **Реализовать периодическое обновление** лент (cron job или queue)
4. **Добавить аутентификацию** (опционально, если нужна мультипользовательская система)
5. **База данных** - PostgreSQL/MongoDB для хранения пользователей, лент, статей, папок

## Зависимости (package.json)
```json
{
  "dependencies": {
    "react": "^18.x",
    "react-dom": "^18.x",
    "react-router": "^7.x",
    "react-dnd": "^16.x",
    "react-dnd-html5-backend": "^16.x",
    "lucide-react": "^0.x",
    "@radix-ui/*": "...", // UI компоненты
    "date-fns": "^4.x" // работа с датами
  }
}
```

## Примечания
- Все тексты интерфейса на русском языке
- Используется TypeScript для type safety
- Компоненты следуют React best practices
- Стили через Tailwind CSS v4
- Проект использует Vite как dev server (уже настроен)
