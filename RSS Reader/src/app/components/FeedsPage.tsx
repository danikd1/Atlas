import { useState, useEffect, type ReactNode } from "react";
import { useOutletContext } from "react-router";
import { Plus, ExternalLink, Eye, EyeOff, Rss, Layers, X, ArrowLeft, Loader2, AlertTriangle, LayoutGrid, Link as LinkIcon, Clock, BellOff, CheckCircle2 } from "lucide-react";
import { RSSFeed, OutletCtx } from "../types";
import { api, apiFeedToRSSFeed, FeedValidateResponse } from "../lib/api";
import { toast } from "sonner";

function getDomain(url: string): string {
  try { return new URL(url).hostname; } catch { return url; }
}

function formatSourceName(domain: string): string {
  const stripped = domain.replace(/^www\./, "");
  const parts = stripped.split(".");
  if (parts.length <= 2) return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
  return parts.slice(0, -1).map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

function commonNamePrefix(names: string[]): string | null {
  if (names.length === 0) return null;
  const words = names[0].split(" ");
  const prefix: string[] = [];
  for (const word of words) {
    const candidate = [...prefix, word].join(" ").toLowerCase();
    if (names.every(n => n.toLowerCase().startsWith(candidate))) prefix.push(word);
    else break;
  }
  return prefix.length > 0 ? prefix.join(" ") : null;
}

function getSourceName(domain: string, feeds: RSSFeed[]): string {
  if (feeds.length === 1) return feeds[0].title;
  return commonNamePrefix(feeds.map(f => f.title)) ?? formatSourceName(domain);
}

// ── Modal: список лент домена ─────────────────────────────────────────────────
function FeedsModal({
  domain, feeds, onClose, onRemove, onToggle,
}: {
  domain: string;
  feeds: RSSFeed[];
  onClose: () => void;
  onRemove: (f: RSSFeed) => void;
  onToggle: (f: RSSFeed) => void;
}) {
  const activeFeeds = feeds.filter(f => f.disabled_reason !== "quiet");
  const quietFeeds = feeds.filter(f => f.disabled_reason === "quiet");

  const FeedRow = ({ feed }: { feed: RSSFeed }) => {
    const isQuiet = feed.disabled_reason === "quiet";
    const lastFetched = feed.addedAt
      ? new Date(feed.addedAt).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })
      : null;

    return (
      <div className={`flex items-start gap-3 px-5 py-3.5 transition-colors ${isQuiet ? "opacity-50" : "hover:bg-gray-50"}`}>
        <div className="flex-shrink-0 mt-0.5">
          {feed.favicon_url
            ? <img src={feed.favicon_url} alt="" className="w-5 h-5 rounded" onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
            : <Rss className={`w-4 h-4 ${isQuiet ? "text-gray-300" : "text-gray-400"}`} />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className={`text-sm font-medium truncate ${isQuiet ? "text-gray-400" : "text-gray-900"}`}>{feed.title}</p>
            {isQuiet && (
              <span className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-400 px-2 py-0.5 rounded-full">
                <BellOff className="w-3 h-3" />Нет статей
              </span>
            )}
            {!isQuiet && feed.hidden && (
              <span className="text-xs text-amber-500 flex items-center gap-1"><EyeOff className="w-3 h-3" />скрыта</span>
            )}
            {!isQuiet && (feed.error_count ?? 0) > 0 && (
              <span className="text-xs text-red-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />ошибки</span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5">
            {feed.category && <span className="text-xs text-gray-400">{feed.category}</span>}
            {!isQuiet && feed.unread_count != null && feed.unread_count > 0 && (
              <span className="text-xs text-blue-500 font-medium">{feed.unread_count} непрочитанных</span>
            )}
            {isQuiet && <span className="text-xs text-gray-400">Ждём публикаций</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <a
            href={feed.url} target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            title="Открыть ленту"
          >
            <ExternalLink className="w-3.5 h-3.5 text-gray-400" />
          </a>
          {!isQuiet && (
            <button
              onClick={() => onToggle(feed)}
              className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              title={feed.hidden ? "Показать в сайдбаре" : "Скрыть из сайдбара"}
            >
              {feed.hidden
                ? <Eye className="w-3.5 h-3.5 text-gray-400" />
                : <EyeOff className="w-3.5 h-3.5 text-gray-400" />
              }
            </button>
          )}
          <button
            onClick={() => onRemove(feed)}
            className="p-1.5 hover:bg-red-50 rounded-lg transition-colors group"
            title="Отписаться"
          >
            <X className="w-3.5 h-3.5 text-gray-300 group-hover:text-red-500 transition-colors" />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />
      <div
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            {feeds[0]?.favicon_url
              ? <img src={feeds[0].favicon_url} alt="" className="w-6 h-6 rounded" />
              : <Layers className="w-5 h-5 text-blue-500" />
            }
            <div>
              <p className="font-semibold text-gray-900 leading-none">{getSourceName(domain, feeds)}</p>
              <div className="flex items-center gap-2 mt-0.5">
                {activeFeeds.length > 0 && (
                  <span className="text-xs text-green-600 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" />{activeFeeds.length} активных
                  </span>
                )}
                {quietFeeds.length > 0 && (
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <BellOff className="w-3 h-3" />{quietFeeds.length} без статей
                  </span>
                )}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* Feed list */}
        <div className="overflow-y-auto flex-1">
          {activeFeeds.length > 0 && (
            <div>
              {activeFeeds.length > 0 && quietFeeds.length > 0 && (
                <p className="px-5 pt-3 pb-1 text-xs font-medium text-gray-400 uppercase tracking-wide">Активные</p>
              )}
              <div className="divide-y divide-gray-50">
                {activeFeeds.map(feed => <FeedRow key={feed.id} feed={feed} />)}
              </div>
            </div>
          )}
          {quietFeeds.length > 0 && (
            <div>
              <p className="px-5 pt-3 pb-1 text-xs font-medium text-gray-400 uppercase tracking-wide">Ждут публикаций</p>
              <div className="divide-y divide-gray-50">
                {quietFeeds.map(feed => <FeedRow key={feed.id} feed={feed} />)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon }: { label: string; value: number | string; icon: ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-4 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600 flex-shrink-0">
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900 leading-none">{value}</p>
        <p className="text-xs text-gray-500 mt-1">{label}</p>
      </div>
    </div>
  );
}

// ── Source card ───────────────────────────────────────────────────────────────
function SourceCard({
  domain, feeds, onClick, onRemove, onToggle,
}: {
  domain: string;
  feeds: RSSFeed[];
  onClick: () => void;
  onRemove: (f: RSSFeed) => void;
  onToggle: (f: RSSFeed) => void;
}) {
  const first = feeds[0];
  const sourceName = getSourceName(domain, feeds);
  const activeFeeds = feeds.filter(f => f.disabled_reason !== "quiet");
  const quietFeeds = feeds.filter(f => f.disabled_reason === "quiet");
  const allQuiet = activeFeeds.length === 0;
  const isHidden = activeFeeds.every(f => f.hidden) && activeFeeds.length > 0;
  const someHidden = activeFeeds.some(f => f.hidden) && !isHidden;
  const unread = feeds.reduce((s, f) => s + (f.unread_count ?? 0), 0);
  const hasError = activeFeeds.some(f => (f.error_count ?? 0) > 0);
  const categories = Array.from(new Set(feeds.map(f => f.category).filter(Boolean)));

  return (
    <div
      onClick={allQuiet ? undefined : onClick}
      className={`bg-white rounded-2xl border overflow-hidden transition-all duration-200 ${
        allQuiet
          ? "border-gray-200 opacity-60 cursor-default"
          : isHidden
            ? "border-gray-200 opacity-60 cursor-pointer hover:shadow-xl hover:-translate-y-1 hover:border-blue-200"
            : "border-gray-100 cursor-pointer hover:shadow-xl hover:-translate-y-1 hover:border-blue-200"
      }`}
    >
      {/* Цветная полоска сверху */}
      <div className={`h-1 w-full ${allQuiet ? "bg-gray-200" : isHidden ? "bg-gray-200" : "bg-blue-400"}`} />

      <div className="p-5 flex flex-col gap-4">
        {/* Top row */}
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center flex-shrink-0 shadow-sm">
            {first.favicon_url
              ? <img src={first.favicon_url} alt="" className="w-7 h-7 rounded-lg" onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
              : <Rss className={`w-5 h-5 ${allQuiet ? "text-gray-300" : "text-gray-400"}`} />
            }
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className={`font-semibold truncate ${allQuiet ? "text-gray-400" : "text-gray-900"}`}>{sourceName}</h3>
              {unread > 0 && (
                <span className="text-xs font-bold bg-blue-500 text-white px-1.5 py-0.5 rounded-full leading-none">{unread}</span>
              )}
              {hasError && <AlertTriangle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-gray-400 flex items-center gap-1">
                {feeds.length > 1 ? <Layers className="w-3 h-3" /> : <Rss className="w-3 h-3" />}
                {feeds.length > 1 ? `${feeds.length} лент` : "1 лента"}
              </span>
              {allQuiet && <span className="text-xs text-gray-400 flex items-center gap-1"><BellOff className="w-3 h-3" />нет статей</span>}
              {!allQuiet && quietFeeds.length > 0 && <span className="text-xs text-gray-400">{quietFeeds.length} без статей</span>}
              {isHidden && <span className="text-xs text-amber-500 flex items-center gap-1"><EyeOff className="w-3 h-3" />скрыто</span>}
              {someHidden && <span className="text-xs text-amber-400">часть скрыта</span>}
            </div>
          </div>
        </div>

        {/* Categories */}
        {categories.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {categories.slice(0, 3).map(cat => (
              <span key={cat} className="text-xs text-gray-500 bg-gray-100 px-2.5 py-1 rounded-full">{cat}</span>
            ))}
            {categories.length > 3 && (
              <span className="text-xs text-gray-400 bg-gray-50 px-2.5 py-1 rounded-full">+{categories.length - 3}</span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-3 border-t border-gray-100" onClick={e => e.stopPropagation()}>
          {!allQuiet && (
            <button
              onClick={() => onToggle(first)}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                isHidden ? "text-amber-600 hover:bg-amber-50" : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {isHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
              {isHidden ? "Показать" : "Скрыть"}
            </button>
          )}
          <button
            onClick={() => onRemove(first)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium text-red-400 hover:bg-red-50 hover:text-red-600 transition-colors ml-auto"
          >
            <X className="w-3.5 h-3.5" />
            Отписаться
          </button>
        </div>
      </div>
    </div>
  );
}

// ── FeedsPage ─────────────────────────────────────────────────────────────────
export function FeedsPage() {
  const ctx = useOutletContext<OutletCtx | undefined>();
  const setSelectedSource = ctx?.setSelectedSource;

  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [modalDomain, setModalDomain] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const [urlInput, setUrlInput] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [validateError, setValidateError] = useState("");
  const [previewData, setPreviewData] = useState<FeedValidateResponse | null>(null);
  const [previewName, setPreviewName] = useState("");
  const [previewCategory, setPreviewCategory] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  useEffect(() => { loadFeeds(); }, []);

  const loadFeeds = async () => {
    try {
      const apiFeeds = await api.getFeeds(true, true);
      setFeeds(apiFeeds.map(apiFeedToRSSFeed));
    } catch (e) { console.error(e); }
  };

  const resetForm = () => {
    setShowAddForm(false); setUrlInput(""); setValidateError("");
    setPreviewData(null); setPreviewName(""); setPreviewCategory("");
    setIsAdding(false);
  };

  const handleValidate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setIsValidating(true); setValidateError("");
    try {
      const result = await api.validateFeed(urlInput.trim());
      if (!result.valid) { setValidateError(result.error ?? "Не удалось проверить ленту."); return; }
      setPreviewData(result); setPreviewName(result.name ?? ""); setPreviewCategory(result.suggested_category ?? "");
    } catch { setValidateError("Ошибка соединения."); }
    finally { setIsValidating(false); }
  };

  const handleConfirmAdd = async () => {
    if (!previewData || !previewName.trim()) return;
    setIsAdding(true);
    try {
      const result = await api.addFeed({
        url: urlInput.trim(), name: previewName.trim(),
        favicon_url: previewData.favicon_url, description: previewData.description,
        category: previewCategory.trim() || null,
      });
      await loadFeeds();
      window.dispatchEvent(new CustomEvent("feeds-updated"));
      resetForm();
      if (result.fetch_status === "quiet") {
        toast(`У ленты "${result.name}" статей пока нет. Она появится в сайдбаре автоматически, как только выйдут новые публикации.`);
      }
    } catch { setValidateError("Ошибка при добавлении."); }
    finally { setIsAdding(false); }
  };

  const handleRemoveFeed = async (feed: RSSFeed) => {
    if (!confirm("Отписаться?")) return;
    const domain = getDomain(feed.url);
    const toRemove = feeds.filter(f => getDomain(f.url) === domain);
    await Promise.all(toRemove.map(f => api.deleteFeed(parseInt(f.id))));
    await loadFeeds();
    window.dispatchEvent(new CustomEvent("feeds-updated"));
    setModalDomain(null);
  };

  const handleToggleVisibility = async (feed: RSSFeed) => {
    const domain = getDomain(feed.url);
    const toUpdate = feeds.filter(f => getDomain(f.url) === domain);
    const newHidden = !feed.hidden;
    await Promise.all(toUpdate.map(f => api.patchFeed(parseInt(f.id), { hidden: newHidden })));
    await loadFeeds();
    window.dispatchEvent(new CustomEvent("feeds-updated"));
  };

  // Одиночные обработчики для модалки — действуют только на конкретную ленту
  const handleRemoveSingleFeed = async (feed: RSSFeed) => {
    if (!confirm(`Отписаться от "${feed.title}"?`)) return;
    await api.deleteFeed(parseInt(feed.id));
    await loadFeeds();
    window.dispatchEvent(new CustomEvent("feeds-updated"));
    // закрыть модалку если лент не осталось
    const remaining = feeds.filter(f => f.id !== feed.id && getDomain(f.url) === getDomain(feed.url));
    if (remaining.length === 0) setModalDomain(null);
  };

  const handleToggleSingleFeed = async (feed: RSSFeed) => {
    await api.patchFeed(parseInt(feed.id), { hidden: !feed.hidden });
    await loadFeeds();
    window.dispatchEvent(new CustomEvent("feeds-updated"));
  };

  // Группировка по домену
  const byDomain = new Map<string, RSSFeed[]>();
  feeds.forEach(f => {
    const d = getDomain(f.url);
    if (!byDomain.has(d)) byDomain.set(d, []);
    byDomain.get(d)!.push(f);
  });
  // Активные домены сначала, потом полностью тихие
  const domains = Array.from(byDomain.entries()).sort(([, aFeeds], [, bFeeds]) => {
    const aAllQuiet = aFeeds.every(f => f.disabled_reason === "quiet");
    const bAllQuiet = bFeeds.every(f => f.disabled_reason === "quiet");
    if (aAllQuiet === bAllQuiet) return 0;
    return aAllQuiet ? 1 : -1;
  });

  // Статистика
  const totalDomains = domains.length;
  const totalFeeds = feeds.length;
  const hiddenCount = domains.filter(([, fs]) => fs.some(f => f.hidden)).length;
  const categories = new Set(feeds.map(f => f.category).filter(Boolean)).size;

  const modalFeeds = modalDomain ? (byDomain.get(modalDomain) ?? []) : [];

  return (
    <div className="max-w-5xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Мои источники</h2>
        <button
          onClick={() => { setIsAdding(false); setShowAddForm(!showAddForm); }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          Добавить источник
        </button>
      </div>

      {/* Stats */}
      {feeds.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          <StatCard label="Источников" value={totalDomains} icon={<LayoutGrid className="w-5 h-5" />} />
          <StatCard label="Лент" value={totalFeeds} icon={<Rss className="w-5 h-5" />} />
          <StatCard label="Скрытых" value={hiddenCount} icon={<EyeOff className="w-5 h-5" />} />
          <StatCard label="Категорий" value={categories} icon={<Layers className="w-5 h-5" />} />
        </div>
      )}

      {/* Add form */}
      {showAddForm && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
          {!previewData ? (
            <>
              <h3 className="text-base font-semibold text-gray-900 mb-4">Добавить по URL</h3>
              <form onSubmit={handleValidate} className="flex gap-3">
                <input
                  type="url" value={urlInput}
                  onChange={e => { setUrlInput(e.target.value); setValidateError(""); }}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="https://example.com/feed.xml"
                  required
                />
                <button type="submit" disabled={isValidating}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-60"
                >
                  {isValidating && <Loader2 className="w-4 h-4 animate-spin" />}
                  Проверить
                </button>
                <button type="button" onClick={resetForm}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm"
                >
                  Отмена
                </button>
              </form>
              {validateError && <p className="mt-2 text-sm text-red-600">{validateError}</p>}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-4">
                <button onClick={() => { setPreviewData(null); setValidateError(""); }} className="p-1 hover:bg-gray-100 rounded transition-colors">
                  <ArrowLeft className="w-4 h-4 text-gray-500" />
                </button>
                <h3 className="text-base font-semibold text-gray-900">Подтвердите добавление</h3>
              </div>
              <div className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg mb-4">
                {previewData.favicon_url
                  ? <img src={previewData.favicon_url} alt="" className="w-7 h-7 rounded flex-shrink-0" />
                  : <Rss className="w-7 h-7 text-gray-400 flex-shrink-0" />
                }
                <div className="flex-1 min-w-0">
                  <a href={urlInput} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline truncate">
                    <LinkIcon className="w-3 h-3" />{urlInput}
                  </a>
                  {previewData.description && <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{previewData.description}</p>}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Название</label>
                  <input type="text" value={previewName} onChange={e => setPreviewName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Категория</label>
                  <input type="text" value={previewCategory} onChange={e => setPreviewCategory(e.target.value)}
                    placeholder="Technology, Design…"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              {validateError && <p className="mb-3 text-sm text-red-600">{validateError}</p>}

              <div className="flex gap-3">
                <button onClick={handleConfirmAdd} disabled={isAdding || !previewName.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm disabled:opacity-60"
                >
                  {isAdding ? <><Loader2 className="w-4 h-4 animate-spin" />Подключаем...</> : "Добавить"}
                </button>
                <button onClick={resetForm} className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm">
                  Отмена
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Empty state */}
      {feeds.length === 0 ? (
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl border-2 border-dashed border-blue-200 p-16 text-center">
          <Rss className="w-14 h-14 text-blue-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Нет источников</h3>
          <p className="text-sm text-gray-500 mb-5">Добавьте первый RSS-источник для начала</p>
          <button onClick={() => setShowAddForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            <Plus className="w-4 h-4" />Добавить источник
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {domains.map(([domain, domainFeeds]) => (
            <SourceCard
              key={domain}
              domain={domain}
              feeds={domainFeeds}
              onClick={() => {
                if (domainFeeds.length === 1 && setSelectedSource) {
                  const f = domainFeeds[0];
                  setSelectedSource({ kind: "feed", feedId: f.id, feedIds: f.feedIds, title: f.title, favicon_url: f.favicon_url });
                } else {
                  setModalDomain(domain);
                }
              }}
              onRemove={handleRemoveFeed}
              onToggle={handleToggleVisibility}
            />
          ))}
        </div>
      )}

      {/* Modal */}
      {modalDomain && (
        <FeedsModal
          domain={modalDomain}
          feeds={modalFeeds}
          onClose={() => setModalDomain(null)}
          onRemove={handleRemoveSingleFeed}
          onToggle={handleToggleSingleFeed}
        />
      )}
    </div>
  );
}
