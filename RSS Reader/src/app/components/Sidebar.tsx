import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import {
  Calendar,
  BookOpen,
  Bookmark,
  Rss,
  Plus,
  ChevronDown,
  ChevronRight,
  Folder as FolderIcon,
  FolderOpen,
  Layers,
  X,
  Check,
  MoreVertical,
  EyeOff,
  Trash2,
  FileText,
  Edit,
  RefreshCw,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { DndProvider, useDrag, useDrop } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { api, apiFeedToRSSFeed, ApiFolder } from "../lib/api";
import { RSSFeed, ArticleSource, sourceKey } from "../types";

const ItemTypes = { FEED: "feed" };

// ─── Collapse state in localStorage ──────────────────────────

function getFolderCollapsed(folderId: string): boolean {
  const stored = localStorage.getItem(`folder_${folderId}_collapsed`);
  // Нет записи = новая папка → свёрнута по умолчанию
  return stored === null ? true : stored === "true";
}

function setFolderCollapsed(folderId: string, collapsed: boolean) {
  localStorage.setItem(`folder_${folderId}_collapsed`, String(collapsed));
}

// ─── DraggableFeed ────────────────────────────────────────────

interface DraggableFeedProps {
  feed: RSSFeed;
  articleCount: number;
  isActive: boolean;
  isInFolder?: boolean;
  onSelect: () => void;
  onHide: (feedId: string) => void;
  onDelete: (feedId: string) => void;
}

function DraggableFeed({
  feed,
  articleCount,
  isActive,
  isInFolder = false,
  onSelect,
  onHide,
  onDelete,
}: DraggableFeedProps) {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: ItemTypes.FEED,
    item: { feedId: feed.id },
    collect: (monitor) => ({ isDragging: monitor.isDragging() }),
  }));

  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative group">
      <button
        ref={drag}
        type="button"
        onClick={onSelect}
        className={`w-full flex items-center justify-between px-3 py-2 pr-8 rounded-md text-sm transition-colors cursor-move text-left ${
          isDragging ? "opacity-50" : ""
        } ${isActive ? "bg-blue-100 text-blue-700" : "text-gray-700 hover:bg-gray-50"}`}
        style={{ opacity: isDragging ? 0.5 : 1 }}
      >
        <div className="flex items-center gap-2 min-w-0">
          {feed.favicon_url ? (
            <img
              src={feed.favicon_url}
              alt=""
              className={`${isInFolder ? "w-3.5 h-3.5" : "w-4 h-4"} flex-shrink-0 rounded-sm`}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <Rss className={`${isInFolder ? "w-3.5 h-3.5" : "w-4 h-4"} flex-shrink-0 text-gray-400`} />
          )}
          <span className={`truncate ${isInFolder ? "text-xs" : ""}`}>{feed.title}</span>
        </div>
        {articleCount > 0 && (
          <span className="text-xs bg-gray-100 text-gray-400 rounded-full px-2 py-0.5 flex-shrink-0 group-hover:opacity-0 transition-opacity">
            {articleCount}
          </span>
        )}
      </button>
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setShowMenu(!showMenu);
        }}
        className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition-all z-10"
      >
        <MoreVertical className="w-3.5 h-3.5 text-gray-500" />
      </button>
      {showMenu && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
          <div className="absolute right-2 top-10 z-20 bg-white border border-gray-200 rounded-md shadow-lg py-1 min-w-[140px]">
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onHide(feed.id);
                setShowMenu(false);
              }}
              className="w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
            >
              <EyeOff className="w-3.5 h-3.5" />
              Скрыть
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete(feed.id);
                setShowMenu(false);
              }}
              className="w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Отписаться
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── DroppableFolder ──────────────────────────────────────────

interface DroppableFolderProps {
  folder: ApiFolder;
  isExpanded: boolean;
  folderUnreadCount: number;
  folderFeeds: RSSFeed[];
  onToggle: () => void;
  onRemove: () => void;
  onRename: (newName: string) => void;
  onDrop: (feedId: string) => void;
  getArticleCountForFeed: (feedId: string) => number;
  activeKey: string | null;
  onSelectFeed: (feed: RSSFeed) => void;
  onSelectFolder: (folder: ApiFolder, feeds: RSSFeed[]) => void;
  onHideFeed: (feedId: string) => void;
  onDeleteFeed: (feedId: string) => void;
}

function DroppableFolder({
  folder,
  isExpanded,
  folderUnreadCount,
  folderFeeds,
  onToggle,
  onRemove,
  onRename,
  onDrop,
  getArticleCountForFeed,
  activeKey,
  onSelectFeed,
  onSelectFolder,
  onHideFeed,
  onDeleteFeed,
}: DroppableFolderProps) {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.FEED,
    drop: (item: { feedId: string }) => onDrop(item.feedId),
    collect: (monitor) => ({ isOver: monitor.isOver() }),
  }));

  const [showMenu, setShowMenu] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(folder.name);

  const confirmRename = () => {
    if (editName.trim() && editName !== folder.name) onRename(editName.trim());
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditName(folder.name);
  };

  return (
    <div ref={drop} className="mb-1">
      <div
        className={`flex items-center justify-between group transition-colors rounded-md relative ${
          isOver ? "bg-blue-50 ring-2 ring-blue-300" : ""
        }`}
      >
        {isEditing ? (
          <div className="flex-1 flex items-center gap-1 px-3 py-2">
            {folder.favicon_url ? (
              <img
                src={folder.favicon_url}
                alt=""
                className="w-4 h-4 flex-shrink-0 rounded-sm"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            ) : (
              <FolderIcon className="w-4 h-4 text-blue-400 flex-shrink-0" />
            )}
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmRename();
                if (e.key === "Escape") handleCancelEdit();
              }}
              className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <button type="button" onClick={confirmRename} className="p-1 hover:bg-green-100 rounded transition-colors">
              <Check className="w-3 h-3 text-green-600" />
            </button>
            <button type="button" onClick={handleCancelEdit} className="p-1 hover:bg-gray-100 rounded transition-colors">
              <X className="w-3 h-3 text-gray-500" />
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={onToggle}
              className="flex-1 flex items-center gap-2 px-3 py-2 pr-8 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              {isExpanded ? (
                <ChevronDown className="w-3 h-3 flex-shrink-0" />
              ) : (
                <ChevronRight className="w-3 h-3 flex-shrink-0" />
              )}
              {folder.favicon_url ? (
                <img
                  src={folder.favicon_url}
                  alt=""
                  className="w-4 h-4 flex-shrink-0 rounded-sm"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : isExpanded ? (
                <FolderOpen className="w-4 h-4 flex-shrink-0 text-blue-400" />
              ) : (
                <FolderIcon className="w-4 h-4 flex-shrink-0 text-blue-400" />
              )}
              <span className="truncate">{folder.name}</span>
              {folderUnreadCount > 0 && (
                <span className="text-xs bg-gray-100 text-gray-400 rounded-full px-2 py-0.5 group-hover:opacity-0 transition-opacity">
                  {folderUnreadCount}
                </span>
              )}
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition-all z-10"
            >
              <MoreVertical className="w-3.5 h-3.5 text-gray-500" />
            </button>
            {showMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                <div className="absolute right-2 top-10 z-20 bg-white border border-gray-200 rounded-md shadow-lg py-1 min-w-[140px]">
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setIsEditing(true);
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                  >
                    <Edit className="w-3.5 h-3.5" />
                    Переименовать
                  </button>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onRemove();
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Удалить
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>

      {isExpanded && (
        <div className="ml-6 mt-1 space-y-1">
          {folderFeeds.length === 0 ? (
            <p className="text-xs text-gray-400 px-3 py-1">Перетащите источник сюда</p>
          ) : (
            <>
              {/* "Все ленты" aggregator */}
              {(() => {
                const allFeedsKey = `feed:${folderFeeds[0]?.id}:all`;
                const isAllActive = activeKey === allFeedsKey;
                return (
                  <button
                    type="button"
                    onClick={() => onSelectFolder(folder, folderFeeds)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-xs transition-colors text-left ${
                      isAllActive ? "bg-blue-100 text-blue-700" : "text-gray-500 hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Layers className="w-3.5 h-3.5 flex-shrink-0 text-blue-300" />
                      <span className="truncate">Общая лента</span>
                    </div>
                    {folderUnreadCount > 0 && (
                      <span className="text-xs bg-gray-100 text-gray-400 rounded-full px-2 py-0.5 flex-shrink-0">
                        {folderUnreadCount}
                      </span>
                    )}
                  </button>
                );
              })()}
              {folderFeeds.map((feed) => (
                <DraggableFeed
                  key={feed.id}
                  feed={feed}
                  articleCount={getArticleCountForFeed(feed.id)}
                  isActive={activeKey === `feed:${feed.id}`}
                  isInFolder
                  onSelect={() => onSelectFeed(feed)}
                  onHide={onHideFeed}
                  onDelete={onDeleteFeed}
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── DroppableRootArea ────────────────────────────────────────

function DroppableRootArea({
  children,
  onDrop,
}: {
  children: React.ReactNode;
  onDrop: (feedId: string) => void;
}) {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.FEED,
    drop: (item: { feedId: string }) => onDrop(item.feedId),
    collect: (monitor) => ({ isOver: monitor.isOver() }),
  }));

  return (
    <div ref={drop} className={`transition-colors rounded-md ${isOver ? "bg-blue-50 ring-2 ring-blue-300" : ""}`}>
      {children}
    </div>
  );
}

// ─── SidebarContent ───────────────────────────────────────────

interface SidebarContentProps {
  selectedSource: ArticleSource | null;
  setSelectedSource: (source: ArticleSource | null) => void;
}

function SidebarContent({ selectedSource, setSelectedSource }: SidebarContentProps) {
  const navigate = useNavigate();
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [folders, setFolders] = useState<ApiFolder[]>([]);
  const [todayCount, setTodayCount] = useState(0);
  const [feedsExpanded, setFeedsExpanded] = useState(true);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [rssStatus, setRssStatus] = useState<{
    last_run_at: string | null;
    next_run_at: string | null;
    is_running: boolean;
    last_new_articles: number | null;
    text_extraction_running: boolean;
    text_extraction_pending: number;
  } | null>(null);
  const [isCollecting, setIsCollecting] = useState(false);

  const activeKey = sourceKey(selectedSource);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const handler = () => loadData();
    window.addEventListener("feeds-updated", handler);
    return () => window.removeEventListener("feeds-updated", handler);
  }, []);

  useEffect(() => {
    const loadStatus = async () => {
      try {
        const status = await api.getRssStatus();
        setRssStatus(status);
        setIsCollecting(status.is_running);
      } catch {}
    };
    loadStatus();
    const interval = setInterval(loadStatus, 60_000);
    return () => clearInterval(interval);
  }, []);

  const handleCollect = async () => {
    if (isCollecting) return;
    setIsCollecting(true);
    try {
      await api.triggerCollect();
      const status = await api.getRssStatus();
      setRssStatus(status);
      await loadData();
      window.dispatchEvent(new CustomEvent("feeds-updated"));
    } catch (e: any) {
      if (e?.message !== "already_running") console.error("Ошибка сбора:", e);
    } finally {
      setIsCollecting(false);
    }
  };

  const loadData = async () => {
    try {
      const [apiFeeds, apiFolders, todayArticles] = await Promise.all([
        api.getFeeds(),
        api.getFolders(),
        api.getTodayArticles(),
      ]);
      setFeeds(apiFeeds.map(apiFeedToRSSFeed));
      setFolders(apiFolders);
      setTodayCount(todayArticles.length);

      setExpandedFolders((prev) => {
        const next = new Set(prev);
        apiFolders.forEach((f) => {
          const id = f.id.toString();
          if (!getFolderCollapsed(id)) next.add(id);
        });
        return next;
      });
    } catch (e) {
      console.error("Ошибка загрузки данных сайдбара:", e);
    }
  };

  const unreadCount = feeds.reduce((sum, f) => sum + (f.unread_count ?? 0), 0);

  const getArticleCountForFeed = (feedId: string) =>
    feeds.find((f) => f.id === feedId)?.unread_count ?? 0;

  const toggleFolder = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
        setFolderCollapsed(folderId, true);
      } else {
        next.add(folderId);
        setFolderCollapsed(folderId, false);
      }
      return next;
    });
  };

  const handleAddFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    try {
      await api.createFolder(newFolderName.trim());
      setNewFolderName("");
      setShowNewFolderInput(false);
      await loadData();
    } catch (e) {
      console.error("Ошибка при создании папки:", e);
    }
  };

  const handleRemoveFolder = async (folderId: string) => {
    if (!confirm("Удалить папку? Источники в ней не будут удалены.")) return;
    try {
      await api.deleteFolder(parseInt(folderId));
      await loadData();
    } catch (e) {
      console.error("Ошибка при удалении папки:", e);
    }
  };

  const handleRenameFolder = async (folderId: string, newName: string) => {
    try {
      await api.patchFolder(parseInt(folderId), { name: newName });
      await loadData();
    } catch (e) {
      console.error("Ошибка при переименовании папки:", e);
    }
  };

  const handleMoveFeedToFolder = async (feedId: string, folderId: string | undefined) => {
    try {
      await api.patchFeed(parseInt(feedId), { folder_id: folderId ? parseInt(folderId) : null });
      await loadData();
    } catch (e) {
      console.error("Ошибка при перемещении ленты:", e);
    }
  };

  const handleToggleFeedHidden = async (feedId: string) => {
    const feed = feeds.find((f) => f.id === feedId);
    try {
      await api.patchFeed(parseInt(feedId), { hidden: !feed?.hidden });
      if (selectedSource?.kind === "feed" && selectedSource.feedId === feedId) {
        setSelectedSource(null);
      }
      await loadData();
    } catch (e) {
      console.error("Ошибка при скрытии ленты:", e);
    }
  };

  const handleRemoveFeed = async (feedId: string) => {
    if (!confirm("Отписаться от источника?")) return;
    try {
      await api.deleteFeed(parseInt(feedId));
      if (selectedSource?.kind === "feed" && selectedSource.feedId === feedId) {
        setSelectedSource(null);
      }
      await loadData();
    } catch (e) {
      console.error("Ошибка при удалении ленты:", e);
    }
  };

  const handleSelectFeed = (feed: RSSFeed) => {
    // Toggle: повторный клик на активную ленту — закрывает панель
    if (activeKey === `feed:${feed.id}`) {
      setSelectedSource(null);
      return;
    }
    setSelectedSource({
      kind: "feed",
      feedId: feed.id,
      feedIds: feed.feedIds,
      title: feed.title,
      favicon_url: feed.favicon_url,
    });
  };

  const handleSelectFolder = (folder: ApiFolder, folderFeeds: RSSFeed[]) => {
    if (folderFeeds.length === 0) return;
    const allFeedsKey = `feed:${folderFeeds[0].id}:all`;
    if (activeKey === allFeedsKey) {
      setSelectedSource(null);
      return;
    }
    setSelectedSource({
      kind: "feed",
      feedId: `${folderFeeds[0].id}:all`,
      feedIds: folderFeeds.map((f) => parseInt(f.id)),
      title: folder.name,
      favicon_url: folder.favicon_url ?? undefined,
    });
  };

  const handleSelectSmart = (kind: "today" | "unread" | "saved" | "all") => {
    if (activeKey === kind) {
      setSelectedSource(null);
      return;
    }
    setSelectedSource({ kind });
  };

  const visibleFeeds = feeds.filter((f) => !f.hidden);
  const feedsWithoutFolder = visibleFeeds.filter((f) => !f.folderId);

  const smartButtonClass = (kind: string) =>
    `w-full flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors text-left ${
      activeKey === kind ? "bg-blue-100 text-blue-700" : "text-gray-700 hover:bg-gray-100"
    }`;

  return (
    <aside className="w-full bg-white border-r border-gray-200 h-full overflow-y-auto flex-shrink-0">
      <div className="p-4 space-y-6">
        {/* Quick Links */}
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Обзор</h3>
          <nav className="space-y-1">
            <button type="button" onClick={() => handleSelectSmart("today")} className={smartButtonClass("today")}>
              <div className="flex items-center gap-3">
                <Calendar className="w-4 h-4" />
                <span>Сегодня</span>
              </div>
              {todayCount > 0 && (
                <span className="text-xs bg-blue-600 text-white rounded-full px-2 py-0.5">{todayCount}</span>
              )}
            </button>

            <button type="button" onClick={() => handleSelectSmart("unread")} className={smartButtonClass("unread")}>
              <div className="flex items-center gap-3">
                <BookOpen className="w-4 h-4" />
                <span>Непрочитанное</span>
              </div>
              {unreadCount > 0 && (
                <span className="text-xs bg-blue-600 text-white rounded-full px-2 py-0.5">{unreadCount}</span>
              )}
            </button>

            <button type="button" onClick={() => handleSelectSmart("saved")} className={smartButtonClass("saved")}>
              <div className="flex items-center gap-3">
                <Bookmark className="w-4 h-4" />
                <span>Сохранённое</span>
              </div>
            </button>

            <button type="button" onClick={() => handleSelectSmart("all")} className={smartButtonClass("all")}>
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4" />
                <span>Все посты</span>
              </div>
            </button>
          </nav>
        </div>

        {/* Feeds Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setFeedsExpanded(!feedsExpanded)}
              className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider hover:text-gray-700"
            >
              {feedsExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Источники
            </button>
            <button
              onClick={() => setShowNewFolderInput(!showNewFolderInput)}
              className="p-1 hover:bg-gray-100 rounded transition-colors"
              title="Создать папку"
            >
              <Plus className="w-4 h-4 text-gray-500" />
            </button>
          </div>

          {feedsExpanded && (
            <nav className="space-y-1">
              {showNewFolderInput && (
                <form onSubmit={handleAddFolder} className="flex items-center gap-1 mb-2">
                  <FolderIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <input
                    type="text"
                    value={newFolderName}
                    onChange={(e) => setNewFolderName(e.target.value)}
                    placeholder="Название папки"
                    className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    autoFocus
                  />
                  <button type="submit" className="p-1 hover:bg-green-100 rounded transition-colors">
                    <Check className="w-4 h-4 text-green-600" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowNewFolderInput(false);
                      setNewFolderName("");
                    }}
                    className="p-1 hover:bg-gray-100 rounded transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-500" />
                  </button>
                </form>
              )}

              {folders.map((folder) => {
                const folderId = folder.id.toString();
                const folderFeeds = visibleFeeds.filter((f) => f.folderId === folderId);
                const folderUnreadCount = folderFeeds.reduce((sum, f) => sum + getArticleCountForFeed(f.id), 0);

                return (
                  <DroppableFolder
                    key={folder.id}
                    folder={folder}
                    isExpanded={expandedFolders.has(folderId)}
                    folderUnreadCount={folderUnreadCount}
                    folderFeeds={folderFeeds}
                    onToggle={() => toggleFolder(folderId)}
                    onRemove={() => handleRemoveFolder(folderId)}
                    onRename={(name) => handleRenameFolder(folderId, name)}
                    onDrop={(feedId) => handleMoveFeedToFolder(feedId, folderId)}
                    getArticleCountForFeed={getArticleCountForFeed}
                    activeKey={activeKey}
                    onSelectFeed={handleSelectFeed}
                    onSelectFolder={handleSelectFolder}
                    onHideFeed={handleToggleFeedHidden}
                    onDeleteFeed={handleRemoveFeed}
                  />
                );
              })}

              {feedsWithoutFolder.length === 0 && folders.length === 0 ? (
                <div className="text-center py-4">
                  <p className="text-xs text-gray-500 mb-2">Нет источников</p>
                  <button
                    onClick={() => navigate("/")}
                    className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Добавить первый источник
                  </button>
                </div>
              ) : (
                <DroppableRootArea onDrop={(feedId) => handleMoveFeedToFolder(feedId, undefined)}>
                  <div className="space-y-1">
                    {feedsWithoutFolder.map((feed) => (
                      <DraggableFeed
                        key={feed.id}
                        feed={feed}
                        articleCount={getArticleCountForFeed(feed.id)}
                        isActive={activeKey === `feed:${feed.id}`}
                        onSelect={() => handleSelectFeed(feed)}
                        onHide={handleToggleFeedHidden}
                        onDelete={handleRemoveFeed}
                      />
                    ))}
                  </div>
                </DroppableRootArea>
              )}
            </nav>
          )}
        </div>
      </div>

      {/* RSS Status */}
      <div className="border-t border-gray-100 px-4 py-3 mt-auto">
        <div className="flex items-center justify-between">
          <div className="min-w-0 flex-1">
            {rssStatus?.last_run_at ? (
              <p className="text-xs text-gray-500 truncate">
                Обновлено{" "}
                {formatDistanceToNow(new Date(rssStatus.last_run_at), {
                  addSuffix: true,
                  locale: ru,
                })}
              </p>
            ) : (
              <p className="text-xs text-gray-400">Ещё не обновлялось</p>
            )}
            {rssStatus?.next_run_at && !isCollecting && (
              <p className="text-xs text-gray-400">
                Следующее{" "}
                {formatDistanceToNow(new Date(rssStatus.next_run_at), {
                  addSuffix: true,
                  locale: ru,
                })}
              </p>
            )}
            {isCollecting && <p className="text-xs text-blue-500">Обновление...</p>}
            {!isCollecting && rssStatus?.text_extraction_running && (
              <p className="text-xs text-blue-400">Извлекаем тексты...</p>
            )}
            {!isCollecting && !rssStatus?.text_extraction_running && (rssStatus?.text_extraction_pending ?? 0) > 0 && (
              <p className="text-xs text-gray-400">{rssStatus!.text_extraction_pending} статей ждут обработки</p>
            )}
          </div>
          <button
            type="button"
            onClick={handleCollect}
            disabled={isCollecting}
            className="ml-2 p-1.5 rounded hover:bg-gray-100 transition-colors disabled:opacity-50"
            title="Обновить сейчас"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-gray-500 ${isCollecting ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>
    </aside>
  );
}

interface SidebarProps {
  selectedSource: ArticleSource | null;
  setSelectedSource: (source: ArticleSource | null) => void;
}

export function Sidebar({ selectedSource, setSelectedSource }: SidebarProps) {
  return (
    <DndProvider backend={HTML5Backend}>
      <SidebarContent selectedSource={selectedSource} setSelectedSource={setSelectedSource} />
    </DndProvider>
  );
}
