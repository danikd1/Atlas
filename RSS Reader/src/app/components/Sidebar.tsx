import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router";
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
  X,
  Check,
  MoreVertical,
  EyeOff,
  Trash2,
  FileText,
  Edit
} from "lucide-react";
import { DndProvider, useDrag, useDrop } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import {
  getArticles,
  getFolders,
  addFolder,
  removeFolder,
  updateFolderName,
} from "../lib/storage";
import { api, apiFeedToRSSFeed } from "../lib/api";
import { RSSFeed, Folder } from "../types";

const ItemTypes = {
  FEED: "feed",
};

interface DraggableFeedProps {
  feed: RSSFeed;
  articleCount: number;
  isActive: boolean;
  isInFolder?: boolean;
  onHide: (feedId: string) => void;
  onDelete: (feedId: string) => void;
}

function DraggableFeed({ feed, articleCount, isActive, isInFolder = false, onHide, onDelete }: DraggableFeedProps) {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: ItemTypes.FEED,
    item: { feedId: feed.id },
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  }));

  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative group">
      <Link
        ref={drag}
        to={`/feed/${feed.id}`}
        className={`flex items-center justify-between px-3 py-2 pr-8 rounded-md text-sm transition-colors cursor-move ${
          isDragging ? "opacity-50" : ""
        } ${
          isActive
            ? "bg-gray-100 text-gray-900"
            : "text-gray-700 hover:bg-gray-50"
        }`}
        style={{ opacity: isDragging ? 0.5 : 1 }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Rss className={`${isInFolder ? "w-3.5 h-3.5" : "w-4 h-4"} flex-shrink-0 text-gray-400`} />
          <span className={`truncate ${isInFolder ? "text-xs" : ""}`}>{feed.title}</span>
        </div>
        {articleCount > 0 && (
          <span className={`text-xs bg-gray-200 text-gray-700 rounded-full px-${isInFolder ? "1.5" : "2"} py-0.5 flex-shrink-0 group-hover:opacity-0 transition-opacity`}>
            {articleCount}
          </span>
        )}
      </Link>
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setShowMenu(!showMenu);
        }}
        className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition-all z-10"
        title="Действия"
      >
        <MoreVertical className="w-3.5 h-3.5 text-gray-500" />
      </button>
      {showMenu && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowMenu(false)}
          />
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
              Удалить
            </button>
          </div>
        </>
      )}
    </div>
  );
}

interface DroppableFolderProps {
  folder: Folder;
  isExpanded: boolean;
  folderUnreadCount: number;
  folderFeeds: RSSFeed[];
  onToggle: () => void;
  onRemove: () => void;
  onRename: (newName: string) => void;
  onDrop: (feedId: string) => void;
  getArticleCountForFeed: (feedId: string) => number;
  currentPath: string;
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
  currentPath,
  onHideFeed,
  onDeleteFeed
}: DroppableFolderProps) {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.FEED,
    drop: (item: { feedId: string }) => {
      onDrop(item.feedId);
    },
    collect: (monitor) => ({
      isOver: monitor.isOver(),
    }),
  }));

  const [showMenu, setShowMenu] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(folder.name);

  const handleRename = (e: React.FormEvent) => {
    e.preventDefault();
    if (editName.trim() && editName !== folder.name) {
      onRename(editName.trim());
    }
    setIsEditing(false);
  };

  return (
    <div ref={drop} className="mb-1">
      <div
        className={`flex items-center justify-between group transition-colors rounded-md relative ${
          isOver ? "bg-blue-50 ring-2 ring-blue-300" : ""
        }`}
      >
        {isEditing ? (
          <form onSubmit={handleRename} className="flex-1 flex items-center gap-1 px-3 py-2">
            <FolderIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
              onBlur={() => {
                setIsEditing(false);
                setEditName(folder.name);
              }}
            />
            <button
              type="submit"
              className="p-1 hover:bg-green-100 rounded transition-colors"
              title="Сохранить"
            >
              <Check className="w-3 h-3 text-green-600" />
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setEditName(folder.name);
              }}
              className="p-1 hover:bg-gray-100 rounded transition-colors"
              title="Отмена"
            >
              <X className="w-3 h-3 text-gray-500" />
            </button>
          </form>
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
              {isExpanded ? (
                <FolderOpen className="w-4 h-4 flex-shrink-0 text-gray-400" />
              ) : (
                <FolderIcon className="w-4 h-4 flex-shrink-0 text-gray-400" />
              )}
              <span className="truncate">{folder.name}</span>
              {folderUnreadCount > 0 && (
                <span className="text-xs bg-gray-200 text-gray-700 rounded-full px-2 py-0.5 group-hover:opacity-0 transition-opacity">
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
              title="Действия"
            >
              <MoreVertical className="w-3.5 h-3.5 text-gray-500" />
            </button>
            {showMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowMenu(false)}
                />
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
            <p className="text-xs text-gray-400 px-3 py-1">
              Перетащите источник сюда
            </p>
          ) : (
            folderFeeds.map((feed) => {
              const articleCount = getArticleCountForFeed(feed.id);
              return (
                <DraggableFeed
                  key={feed.id}
                  feed={feed}
                  articleCount={articleCount}
                  isActive={currentPath === `/feed/${feed.id}`}
                  isInFolder={true}
                  onHide={onHideFeed}
                  onDelete={onDeleteFeed}
                />
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

interface DroppableRootAreaProps {
  children: React.ReactNode;
  onDrop: (feedId: string) => void;
}

function DroppableRootArea({ children, onDrop }: DroppableRootAreaProps) {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.FEED,
    drop: (item: { feedId: string }) => {
      onDrop(item.feedId);
    },
    collect: (monitor) => ({
      isOver: monitor.isOver(),
    }),
  }));

  return (
    <div
      ref={drop}
      className={`transition-colors rounded-md ${
        isOver ? "bg-blue-50 ring-2 ring-blue-300" : ""
      }`}
    >
      {children}
    </div>
  );
}

function SidebarContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [articles, setArticles] = useState<any[]>([]);
  const [feedsExpanded, setFeedsExpanded] = useState(true);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");

  useEffect(() => {
    loadData();
  }, [location.pathname]);

  const loadData = async () => {
    try {
      const apiFeeds = await api.getFeeds();
      setFeeds(apiFeeds.map(apiFeedToRSSFeed));
    } catch (e) {
      console.error("Ошибка загрузки лент:", e);
    }
    setFolders(getFolders());
    setArticles(getArticles());
  };

  // Calculate counts
  const todayCount = articles.filter((article) => {
    const pubDate = new Date(article.pubDate);
    const today = new Date();
    return (
      pubDate.getDate() === today.getDate() &&
      pubDate.getMonth() === today.getMonth() &&
      pubDate.getFullYear() === today.getFullYear()
    );
  }).length;

  // unread_count берётся из API (поле на каждой ленте), saved — пока из localStorage (сценарий 2.1)
  const unreadCount = feeds.reduce((sum, f) => sum + (f.unread_count ?? 0), 0);
  const savedCount = articles.filter((a) => a.saved).length;

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const getArticleCountForFeed = (feedId: string) => {
    return feeds.find((f) => f.id === feedId)?.unread_count ?? 0;
  };

  const handleAddFolder = (e: React.FormEvent) => {
    e.preventDefault();
    if (newFolderName.trim()) {
      addFolder(newFolderName);
      setNewFolderName("");
      setShowNewFolderInput(false);
      loadData();
    }
  };

  const toggleFolder = (folderId: string) => {
    const newSet = new Set(expandedFolders);
    if (newSet.has(folderId)) {
      newSet.delete(folderId);
    } else {
      newSet.add(folderId);
    }
    setExpandedFolders(newSet);
  };

  const handleRemoveFolder = (folderId: string) => {
    if (confirm("Удалить папку? Источники в ней не будут удалены.")) {
      removeFolder(folderId);
      loadData();
    }
  };

  const handleRenameFolder = (folderId: string, newName: string) => {
    updateFolderName(folderId, newName);
    loadData();
  };

  const handleMoveFeedToFolder = (_feedId: string, _folderId: string | undefined) => {
    // Папки будут привязаны к API в сценарии 1.3
    loadData();
  };

  const handleToggleFeedHidden = async (feedId: string) => {
    const feed = feeds.find((f) => f.id === feedId);
    try {
      await api.patchFeed(parseInt(feedId), { hidden: !feed?.hidden });
      await loadData();
    } catch (e) {
      console.error("Ошибка при скрытии ленты:", e);
    }
  };

  const handleRemoveFeed = async (feedId: string) => {
    if (confirm("Удалить источник?")) {
      try {
        await api.deleteFeed(parseInt(feedId));
        await loadData();
      } catch (e) {
        console.error("Ошибка при удалении ленты:", e);
      }
    }
  };

  // Separate feeds by folder - filter hidden feeds
  const visibleFeeds = feeds.filter((f) => !f.hidden);
  const feedsWithoutFolder = visibleFeeds.filter((f) => !f.folderId);

  return (
    <aside className="w-64 bg-white border-r border-gray-200 h-[calc(100vh-4rem)] overflow-y-auto flex-shrink-0">
      <div className="p-4 space-y-6">
        {/* Quick Links Section */}
        <div>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Обзор
          </h3>
          <nav className="space-y-1">
            <Link
              to="/today"
              className={`flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive("/today")
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <div className="flex items-center gap-3">
                <Calendar className="w-4 h-4" />
                <span>Сегодня</span>
              </div>
              {todayCount > 0 && (
                <span className="text-xs bg-blue-600 text-white rounded-full px-2 py-0.5">
                  {todayCount}
                </span>
              )}
            </Link>

            <Link
              to="/unread"
              className={`flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive("/unread")
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <div className="flex items-center gap-3">
                <BookOpen className="w-4 h-4" />
                <span>Непрочитанное</span>
              </div>
              {unreadCount > 0 && (
                <span className="text-xs bg-blue-600 text-white rounded-full px-2 py-0.5">
                  {unreadCount}
                </span>
              )}
            </Link>

            <Link
              to="/saved"
              className={`flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive("/saved")
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <div className="flex items-center gap-3">
                <Bookmark className="w-4 h-4" />
                <span>Сохраненное</span>
              </div>
              {savedCount > 0 && (
                <span className="text-xs bg-blue-600 text-white rounded-full px-2 py-0.5">
                  {savedCount}
                </span>
              )}
            </Link>

            <Link
              to="/articles"
              className={`flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive("/articles")
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4" />
                <span>Все посты</span>
              </div>
            </Link>
          </nav>
        </div>

        {/* Feeds Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setFeedsExpanded(!feedsExpanded)}
              className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wider hover:text-gray-700"
            >
              {feedsExpanded ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
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
              {/* New Folder Input */}
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
                  <button
                    type="submit"
                    className="p-1 hover:bg-green-100 rounded transition-colors"
                    title="Создать"
                  >
                    <Check className="w-4 h-4 text-green-600" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowNewFolderInput(false);
                      setNewFolderName("");
                    }}
                    className="p-1 hover:bg-gray-100 rounded transition-colors"
                    title="Отмена"
                  >
                    <X className="w-4 h-4 text-gray-500" />
                  </button>
                </form>
              )}

              {/* Folders */}
              {folders.map((folder) => {
                const folderFeeds = feeds.filter((f) => f.folderId === folder.id);
                const folderUnreadCount = folderFeeds.reduce(
                  (sum, feed) => sum + getArticleCountForFeed(feed.id),
                  0
                );
                const isExpanded = expandedFolders.has(folder.id);

                return (
                  <DroppableFolder
                    key={folder.id}
                    folder={folder}
                    isExpanded={isExpanded}
                    folderUnreadCount={folderUnreadCount}
                    folderFeeds={folderFeeds}
                    onToggle={() => toggleFolder(folder.id)}
                    onRemove={() => handleRemoveFolder(folder.id)}
                    onRename={(newName) => handleRenameFolder(folder.id, newName)}
                    onDrop={(feedId) => handleMoveFeedToFolder(feedId, folder.id)}
                    getArticleCountForFeed={getArticleCountForFeed}
                    currentPath={location.pathname}
                    onHideFeed={handleToggleFeedHidden}
                    onDeleteFeed={handleRemoveFeed}
                  />
                );
              })}

              {/* Feeds without folder - with drop zone */}
              {feedsWithoutFolder.length === 0 && folders.length === 0 ? (
                <div className="text-center py-4">
                  <p className="text-xs text-gray-500 mb-2">
                    Нет источников
                  </p>
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
                    {feedsWithoutFolder.map((feed) => {
                      const articleCount = getArticleCountForFeed(feed.id);
                      return (
                        <DraggableFeed
                          key={feed.id}
                          feed={feed}
                          articleCount={articleCount}
                          isActive={location.pathname === `/feed/${feed.id}`}
                          onHide={handleToggleFeedHidden}
                          onDelete={handleRemoveFeed}
                        />
                      );
                    })}
                  </div>
                </DroppableRootArea>
              )}
            </nav>
          )}
        </div>
      </div>
    </aside>
  );
}

export function Sidebar() {
  return (
    <DndProvider backend={HTML5Backend}>
      <SidebarContent />
    </DndProvider>
  );
}