import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import { Send, Loader2, Clock, ChevronDown, ChevronRight, AlertTriangle, Play } from "lucide-react";
import { api } from "../lib/api";
import { qaCache, qaCacheKey, type QAHistoryItem, type QASource } from "../lib/qaCache";

interface QAPanelProps {
  feedIds: number[];
  collectionId?: number;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function AnswerCard({
  item,
  onArticleClick,
}: {
  item: QAHistoryItem;
  onArticleClick: (id: number) => void;
}) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-3 space-y-3">
      <div>
        <p className="text-xs text-gray-400 mb-1.5">Ответ · контекст: {item.articleCount} статей</p>
        <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{item.answer}</p>
      </div>

      {item.sources.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-gray-400">Источники</p>
          {item.sources.map((src, i) => (
            <button
              key={src.link}
              onClick={() => src.article_id && onArticleClick(src.article_id)}
              className="w-full text-left flex items-start gap-1.5 px-2 py-1.5 border border-gray-100 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors group"
            >
              <span className="text-xs text-gray-400 font-mono mt-0.5 flex-shrink-0">[{i + 1}]</span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-gray-800 truncate group-hover:text-blue-700">
                  {src.title || src.link}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  {src.feed_name && (
                    <p className="text-xs text-gray-400 truncate">{src.feed_name}</p>
                  )}
                  {src.published_at && (
                    <p className="text-xs text-gray-300 flex-shrink-0">{formatDate(src.published_at)}</p>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryItem({
  item,
  defaultExpanded,
  onArticleClick,
}: {
  item: QAHistoryItem;
  defaultExpanded: boolean;
  onArticleClick: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded]);

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden bg-white">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left flex items-start gap-2 px-3 py-2 hover:bg-gray-50 transition-colors"
      >
        <Clock className="w-3 h-3 text-gray-300 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs text-gray-700 line-clamp-2 leading-snug">{item.question}</p>
          <p className="text-xs text-gray-300 mt-0.5">{formatTime(item.askedAt)}</p>
        </div>
        {expanded
          ? <ChevronDown className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
          : <ChevronRight className="w-3.5 h-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
        }
      </button>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-gray-100 space-y-3">
          <p className="text-xs text-gray-400">Ответ · контекст: {item.articleCount} статей</p>
          <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{item.answer}</p>
          {item.sources.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-400">Источники</p>
              {item.sources.map((src, i) => (
                <button
                  key={src.link}
                  onClick={() => src.article_id && onArticleClick(src.article_id)}
                  className="w-full text-left flex items-start gap-1.5 px-2 py-1.5 border border-gray-100 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors group"
                >
                  <span className="text-xs text-gray-400 font-mono mt-0.5 flex-shrink-0">[{i + 1}]</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-800 truncate group-hover:text-blue-700">
                      {src.title || src.link}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {src.feed_name && (
                        <p className="text-xs text-gray-400 truncate">{src.feed_name}</p>
                      )}
                      {src.published_at && (
                        <p className="text-xs text-gray-300 flex-shrink-0">{formatDate(src.published_at)}</p>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function QAPanel({ feedIds, collectionId }: QAPanelProps) {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<QAHistoryItem[]>([]);
  // Отслеживаем какой элемент "свежий" (раскрыт по умолчанию)
  const [latestQuestion, setLatestQuestion] = useState<string | null>(null);

  const [ragPending, setRagPending] = useState<number | null>(null);
  const [ragIndexed, setRagIndexed] = useState<number | null>(null);
  const [extractionPending, setExtractionPending] = useState(0);
  const [startingIndexer, setStartingIndexer] = useState(false);

  const feedKey = qaCacheKey(feedIds);

  const fetchRagStatus = useCallback(async () => {
    // Skip RAG status check when BERTopic collection is active
    if (collectionId != null) return;
    try {
      const s = await api.getRssStatus();
      setRagPending(s.rag_pending ?? 0);
      setRagIndexed(s.rag_indexed ?? 0);
      setExtractionPending(s.text_extraction_pending ?? 0);
    } catch {
      // ignore
    }
  }, [collectionId]);

  useEffect(() => {
    const h = qaCache.getHistory(feedKey);
    setHistory(h);
    setLatestQuestion(null); // не раскрываем при загрузке из кэша
    setError(null);
    setQuestion("");
  }, [feedKey]);

  useEffect(() => {
    fetchRagStatus();
    const id = setInterval(fetchRagStatus, 15_000);
    return () => clearInterval(id);
  }, [fetchRagStatus]);

  const handleStartIndexer = async () => {
    setStartingIndexer(true);
    try {
      if (extractionPending > 0) {
        await api.startExtractionWorker();
      } else {
        await api.startRagIndexer();
      }
      await fetchRagStatus();
    } catch {
      // ignore
    } finally {
      setStartingIndexer(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await api.feedQA({ feed_ids: feedIds, collection_id: collectionId, question: q });
      if (result.status === "error") {
        setError(result.error || "Неизвестная ошибка");
      } else {
        const item: QAHistoryItem = {
          question: q,
          answer: result.answer ?? "",
          sources: result.sources as QASource[],
          articleCount: result.article_count,
          askedAt: new Date().toISOString(),
        };
        qaCache.push(feedKey, item);
        const updated = qaCache.getHistory(feedKey);
        setHistory([...updated]);
        setLatestQuestion(q);
        setQuestion("");
      }
    } catch (e: any) {
      setError(e.message || "Ошибка запроса");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const ragUnavailable = collectionId == null && ragPending !== null && ragPending > 0;
  const ragTotal = (ragIndexed ?? 0) + (ragPending ?? 0);

  return (
    <div className="border-t border-gray-100 bg-gray-50">
      {/* RAG недоступен — баннер */}
      {ragUnavailable && (
        <div className="mx-3 mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
          <span className="text-xs text-amber-700 flex-1 min-w-0">
            База знаний не готова
            {ragTotal > 0 && <span className="text-amber-500 ml-1">{ragIndexed} / {ragTotal}</span>}
          </span>
          <button
            onClick={handleStartIndexer}
            disabled={startingIndexer}
            className="flex-shrink-0 flex items-center gap-1 text-xs font-medium text-amber-700 hover:text-amber-900 disabled:opacity-50 transition-colors"
          >
            {startingIndexer ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            Запустить
          </button>
        </div>
      )}

      {/* Поле ввода */}
      <form onSubmit={handleSubmit} className="p-3 flex gap-2 items-end">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Задайте вопрос по статьям этой ленты..."
          rows={2}
          disabled={isLoading}
          className="flex-1 resize-none text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!question.trim() || isLoading}
          className="flex-shrink-0 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </form>

      {/* Ошибка */}
      {error && (
        <div className="mx-3 mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Загрузка */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-gray-400 px-3 pb-3">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Ищу ответ...</span>
        </div>
      )}

      {/* История запросов */}
      {history.length > 0 && (
        <div className="px-3 pb-3 space-y-1.5">
          {history.map((item) => (
            <HistoryItem
              key={item.question}
              item={item}
              defaultExpanded={item.question === latestQuestion}
              onArticleClick={(id) => navigate(`/article/${id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
