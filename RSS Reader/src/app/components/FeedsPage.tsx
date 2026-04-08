import { useState, useEffect } from "react";
import { useOutletContext } from "react-router";
import { Plus, ExternalLink, Eye, EyeOff, Rss, Layers, Link as LinkIcon, ArrowLeft, Loader2, AlertTriangle } from "lucide-react";
import { RSSFeed } from "../types";
import { api, apiFeedToRSSFeed, FeedValidateResponse } from "../lib/api";

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export function FeedsPage() {
  const { setSelectedFeed } = useOutletContext<{ setSelectedFeed: (feed: RSSFeed | null) => void }>();
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);

  // Форма: шаг 1 — ввод URL
  const [showAddForm, setShowAddForm] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [validateError, setValidateError] = useState("");

  // Форма: шаг 2 — превью и подтверждение
  const [previewData, setPreviewData] = useState<FeedValidateResponse | null>(null);
  const [previewName, setPreviewName] = useState("");
  const [previewCategory, setPreviewCategory] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  useEffect(() => {
    loadFeeds();
  }, []);

  const loadFeeds = async () => {
    try {
      const apiFeeds = await api.getFeeds();
      setFeeds(apiFeeds.map(apiFeedToRSSFeed));
    } catch (e) {
      console.error("Ошибка загрузки лент:", e);
    }
  };

  const resetForm = () => {
    setShowAddForm(false);
    setUrlInput("");
    setValidateError("");
    setPreviewData(null);
    setPreviewName("");
    setPreviewCategory("");
  };

  // Шаг 1: валидация URL
  const handleValidate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setIsValidating(true);
    setValidateError("");
    try {
      const result = await api.validateFeed(urlInput.trim());
      if (!result.valid) {
        setValidateError(result.error ?? "Не удалось проверить ленту. Проверьте URL.");
        return;
      }
      setPreviewData(result);
      setPreviewName(result.name ?? "");
      setPreviewCategory(result.suggested_category ?? "");
    } catch {
      setValidateError("Ошибка соединения. Проверьте что бэкенд запущен.");
    } finally {
      setIsValidating(false);
    }
  };

  // Шаг 2: подтверждение и сохранение
  const handleConfirmAdd = async () => {
    if (!previewData || !previewName.trim()) return;
    setIsAdding(true);
    try {
      await api.addFeed({
        url: urlInput.trim(),
        name: previewName.trim(),
        favicon_url: previewData.favicon_url,
        description: previewData.description,
        category: previewCategory.trim() || null,
      });
      await loadFeeds();
      resetForm();
    } catch {
      setValidateError("Ошибка при добавлении ленты.");
      setIsAdding(false);
    }
  };

  const handleRemoveFeed = async (feed: RSSFeed) => {
    if (!confirm("Вы уверены, что хотите отписаться?")) return;
    const domain = getDomain(feed.url);
    const sameDomain = feeds.filter((f) => getDomain(f.url) === domain);
    // Удаляем все ленты домена если их больше одной (группа), иначе только текущую
    const toRemove = sameDomain.length > 1 ? sameDomain : [feed];
    try {
      await Promise.all(toRemove.map((f) => api.deleteFeed(parseInt(f.id))));
      await loadFeeds();
    } catch (e) {
      console.error("Ошибка при удалении:", e);
    }
  };

  const handleToggleVisibility = async (feed: RSSFeed) => {
    const domain = getDomain(feed.url);
    const sameDomain = feeds.filter((f) => getDomain(f.url) === domain);
    const toUpdate = sameDomain.length > 1 ? sameDomain : [feed];
    const newHidden = !feed.hidden;
    try {
      await Promise.all(toUpdate.map((f) => api.patchFeed(parseInt(f.id), { hidden: newHidden })));
      await loadFeeds();
    } catch (e) {
      console.error("Ошибка при обновлении:", e);
    }
  };

  // Группировка по домену: 2+ лент → группа, 1 лента → отдельная карточка
  const feedsByDomain = new Map<string, RSSFeed[]>();
  feeds.forEach((feed) => {
    const domain = getDomain(feed.url);
    if (!feedsByDomain.has(domain)) feedsByDomain.set(domain, []);
    feedsByDomain.get(domain)!.push(feed);
  });

  const sourceGroups: Array<{ domain: string; feeds: RSSFeed[] }> = [];
  const standaloneFeeds: RSSFeed[] = [];
  feedsByDomain.forEach((domainFeeds, domain) => {
    if (domainFeeds.length > 1) sourceGroups.push({ domain, feeds: domainFeeds });
    else standaloneFeeds.push(domainFeeds[0]);
  });

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">Мои источники</h2>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Добавить источник
        </button>
      </div>

      {showAddForm && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          {!previewData ? (
            // Шаг 1: ввод URL
            <>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Добавить источник по URL</h3>
              <form onSubmit={handleValidate} className="space-y-4">
                <div>
                  <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-1">
                    URL RSS-ленты
                  </label>
                  <input
                    type="url"
                    id="url"
                    value={urlInput}
                    onChange={(e) => { setUrlInput(e.target.value); setValidateError(""); }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://example.com/feed.xml"
                    required
                  />
                  {validateError && (
                    <p className="mt-1 text-sm text-red-600">{validateError}</p>
                  )}
                </div>
                <div className="flex gap-3">
                  <button
                    type="submit"
                    disabled={isValidating}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-60"
                  >
                    {isValidating && <Loader2 className="w-4 h-4 animate-spin" />}
                    Проверить
                  </button>
                  <button
                    type="button"
                    onClick={resetForm}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                  >
                    Отмена
                  </button>
                </div>
              </form>
            </>
          ) : (
            // Шаг 2: превью и подтверждение
            <>
              <div className="flex items-center gap-2 mb-4">
                <button
                  onClick={() => { setPreviewData(null); setValidateError(""); }}
                  className="p-1 hover:bg-gray-100 rounded transition-colors"
                >
                  <ArrowLeft className="w-4 h-4 text-gray-500" />
                </button>
                <h3 className="text-lg font-medium text-gray-900">Подтвердите добавление</h3>
              </div>

              <div className="flex items-start gap-4 mb-4 p-4 bg-gray-50 rounded-lg">
                {previewData.favicon_url ? (
                  <img src={previewData.favicon_url} alt="" className="w-8 h-8 rounded flex-shrink-0" />
                ) : (
                  <Rss className="w-8 h-8 text-gray-400 flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-500 truncate mb-1">{urlInput}</p>
                  {previewData.description && (
                    <p className="text-sm text-gray-600 line-clamp-2">{previewData.description}</p>
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Название (можно изменить)
                  </label>
                  <input
                    type="text"
                    value={previewName}
                    onChange={(e) => setPreviewName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Категория (можно изменить)
                  </label>
                  <input
                    type="text"
                    value={previewCategory}
                    onChange={(e) => setPreviewCategory(e.target.value)}
                    placeholder="Например: Technology, Design, News"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                {validateError && (
                  <p className="text-sm text-red-600">{validateError}</p>
                )}
                <div className="flex gap-3">
                  <button
                    onClick={handleConfirmAdd}
                    disabled={isAdding || !previewName.trim()}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-60"
                  >
                    {isAdding && <Loader2 className="w-4 h-4 animate-spin" />}
                    Добавить
                  </button>
                  <button
                    onClick={resetForm}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                  >
                    Отмена
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <div className="space-y-3">
        {feeds.length === 0 ? (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border-2 border-dashed border-blue-300 p-12 text-center">
            <Rss className="w-16 h-16 text-blue-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Нет источников</h3>
            <p className="text-gray-600 mb-4">Добавьте первый RSS-источник для начала!</p>
            <button
              onClick={() => setShowAddForm(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Добавить источник
            </button>
          </div>
        ) : (
          <>
            {/* Группы: 2+ ленты с одного домена */}
            {sourceGroups.map(({ domain, feeds: groupFeeds }) => {
              const firstFeed = groupFeeds[0];
              const isHidden = firstFeed.hidden;
              const groupUnread = groupFeeds.reduce((sum, f) => sum + (f.unread_count ?? 0), 0);
              const groupHasErrors = groupFeeds.some((f) => (f.error_count ?? 0) > 0);

              return (
                <div
                  key={domain}
                  onClick={() => setSelectedFeed(firstFeed)}
                  className={`relative overflow-hidden rounded-xl border-2 transition-all hover:shadow-lg cursor-pointer ${
                    isHidden
                      ? "bg-gray-50 border-gray-300 opacity-75"
                      : "bg-gradient-to-br from-blue-50 via-white to-purple-50 border-blue-200 hover:border-blue-300"
                  }`}
                >
                  <div className={`px-5 py-3 border-b ${isHidden ? "bg-gray-100 border-gray-200" : "bg-gradient-to-r from-blue-100 to-purple-100 border-blue-200"}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${isHidden ? "bg-gray-300" : "bg-blue-600"} text-white`}>
                          <Layers className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-gray-900 text-base">{domain}</h3>
                            {groupUnread > 0 && (
                              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 text-xs font-bold bg-blue-600 text-white rounded-full">
                                {groupUnread}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-600">
                            <span className="flex items-center gap-1">
                              <Rss className="w-3 h-3" />
                              {groupFeeds.length} {groupFeeds.length < 5 ? "ленты" : "лент"}
                            </span>
                            {groupHasErrors && (
                              <span className="flex items-center gap-1 text-red-600 font-medium">
                                <AlertTriangle className="w-3 h-3" />
                                Ошибка сбора
                              </span>
                            )}
                            {isHidden && (
                              <span className="flex items-center gap-1 text-amber-600 font-medium">
                                <EyeOff className="w-3 h-3" />
                                Скрыто
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRemoveFeed(firstFeed); }}
                          className="px-3 py-1.5 text-xs font-medium text-red-700 bg-red-100 rounded-lg hover:bg-red-200 transition-colors"
                        >
                          Отписаться
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleToggleVisibility(firstFeed); }}
                          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                            isHidden ? "text-green-700 bg-green-100 hover:bg-green-200" : "text-gray-700 bg-gray-200 hover:bg-gray-300"
                          }`}
                        >
                          {isHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                          {isHidden ? "Показать" : "Скрыть"}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="px-5 py-3 space-y-2">
                    {groupFeeds.map((feed) => (
                      <div
                        key={feed.id}
                        className={`flex items-start gap-3 p-3 rounded-lg transition-colors ${
                          isHidden ? "bg-white/50" : "bg-white hover:bg-blue-50/50"
                        }`}
                      >
                        <div className={`mt-0.5 w-1 h-full rounded-full ${isHidden ? "bg-gray-300" : "bg-gradient-to-b from-blue-400 to-purple-400"}`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-0.5">
                            <h4 className="font-medium text-gray-900 text-sm">{feed.title}</h4>
                            {feed.category && (
                              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded whitespace-nowrap flex-shrink-0">{feed.category}</span>
                            )}
                          </div>
                          {feed.description && (
                            <p className="text-xs text-gray-500 mb-1 line-clamp-1">{feed.description}</p>
                          )}
                          <a
                            href={feed.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 hover:underline"
                          >
                            <LinkIcon className="w-3 h-3" />
                            <span className="truncate max-w-md">{feed.url}</span>
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}

            {/* Одиночные ленты */}
            {standaloneFeeds.map((feed) => {
              const isHidden = feed.hidden;

              return (
                <div
                  key={feed.id}
                  onClick={() => setSelectedFeed(feed)}
                  className={`relative overflow-hidden rounded-xl border-2 transition-all hover:shadow-lg cursor-pointer ${
                    isHidden
                      ? "bg-gray-50 border-gray-300 opacity-75"
                      : "bg-gradient-to-br from-emerald-50 via-white to-teal-50 border-emerald-200 hover:border-emerald-300"
                  }`}
                >
                  <div className="p-5">
                    <div className="flex items-start gap-4">
                      <div className={`p-2 rounded-xl flex-shrink-0 ${isHidden ? "bg-gray-200" : "bg-gradient-to-br from-emerald-500 to-teal-500"}`}>
                        {feed.favicon_url ? (
                          <img src={feed.favicon_url} alt="" className="w-6 h-6 rounded" />
                        ) : (
                          <Rss className={`w-6 h-6 ${isHidden ? "text-gray-400" : "text-white"}`} />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="font-semibold text-gray-900 text-base">{feed.title}</h3>
                              {(feed.unread_count ?? 0) > 0 && (
                                <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 text-xs font-bold bg-emerald-500 text-white rounded-full">
                                  {feed.unread_count}
                                </span>
                              )}
                            </div>
                            {(feed.error_count ?? 0) > 0 && (
                              <span className="inline-flex items-center gap-1 text-xs text-red-600 font-medium mb-1" title={feed.last_error ?? undefined}>
                                <AlertTriangle className="w-3 h-3" />
                                Ошибка сбора — наведите для деталей
                              </span>
                            )}
                            {isHidden && (
                              <span className="inline-flex items-center gap-1 text-xs text-amber-600 font-medium mb-2">
                                <EyeOff className="w-3 h-3" />
                                Скрыто из меню
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRemoveFeed(feed); }}
                              className="px-3 py-1.5 text-xs font-medium text-red-700 bg-red-100 rounded-lg hover:bg-red-200 transition-colors"
                            >
                              Отписаться
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleToggleVisibility(feed); }}
                              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                                isHidden ? "text-green-700 bg-green-100 hover:bg-green-200" : "text-gray-700 bg-gray-200 hover:bg-gray-300"
                              }`}
                            >
                              {isHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                              {isHidden ? "Показать" : "Скрыть"}
                            </button>
                          </div>
                        </div>

                        <div className="flex items-start justify-between gap-2 mt-1">
                          {feed.description ? (
                            <p className="text-xs text-gray-500 line-clamp-2">{feed.description}</p>
                          ) : <span />}
                          {feed.category && (
                            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded whitespace-nowrap flex-shrink-0">{feed.category}</span>
                          )}
                        </div>
                        <a
                          href={feed.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 hover:underline"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span className="truncate max-w-md">{feed.url}</span>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
