import { useState, useEffect, useRef } from "react";
import { useOutletContext } from "react-router";
import { RefreshCw, Loader2, Map, AlertCircle } from "lucide-react";
import { api } from "../lib/api";
import { BubbleMap, type TopicBubble } from "./BubbleMap";
import type { OutletCtx } from "../types";

type TaskStatus = "idle" | "pending" | "running" | "done" | "error";

export function TopicMapPage() {
  const { setSelectedSource } = useOutletContext<OutletCtx>();

  const [topics, setTopics] = useState<TopicBubble[]>([]);
  const [isLoadingTopics, setIsLoadingTopics] = useState(true);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);

  const [taskStatus, setTaskStatus] = useState<TaskStatus>("idle");
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState("");
  const [taskError, setTaskError] = useState<string | null>(null);
  const [daysBack, setDaysBack] = useState(30);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    loadTopics();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const loadTopics = async () => {
    setIsLoadingTopics(true);
    try {
      const data = await api.bertopicTopics();
      setTopics(data.topics.map(t => ({
        id: t.id,
        name: t.name,
        keywords: t.keywords,
        description: t.description ?? undefined,
        article_count: t.article_count,
      })));
    } catch {
      setTopics([]);
    } finally {
      setIsLoadingTopics(false);
    }
  };

  const handleRun = async () => {
    setTaskStatus("pending");
    setTaskProgress(0);
    setTaskMessage("Запускаем пайплайн...");
    setTaskError(null);
    try {
      const result = await api.bertopicRun({ skip_rag: true, days_back: daysBack });
      startPolling(result.task_id);
    } catch (e: any) {
      setTaskStatus("error");
      setTaskError(e.message || "Ошибка запуска");
    }
  };

  const startPolling = (id: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.bertopicStatus(id);
        setTaskProgress(s.progress);
        setTaskMessage(s.message);
        setTaskStatus(s.status as TaskStatus);
        if (s.status === "done") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          loadTopics();
        } else if (s.status === "error") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setTaskError(s.error || "Неизвестная ошибка");
        }
      } catch { /* продолжаем пробовать */ }
    }, 2000);
  };

  const handleSelectTopic = (topic: TopicBubble) => {
    setSelectedTopicId(topic.id);
    setSelectedSource({
      kind: "topic",
      collectionId: topic.id,
      title: topic.name,
      keywords: topic.keywords,
    });
  };

  const isRunning = taskStatus === "pending" || taskStatus === "running";

  return (
    <div className="h-full flex flex-col overflow-hidden -mx-4 sm:-mx-6 lg:-mx-8 -my-8">
      {/* Шапка */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Map className="w-5 h-5 text-blue-600" />
          <h1 className="text-base font-semibold text-gray-900">Карта тем</h1>
          {topics.length > 0 && (
            <span className="text-xs text-gray-400 ml-1">{topics.length} тем</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Ползунок: период статей */}
          {!isRunning && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 whitespace-nowrap">За последние</span>
              <input
                type="range"
                min={7}
                max={90}
                step={7}
                value={daysBack}
                onChange={(e) => setDaysBack(Number(e.target.value))}
                className="w-24 accent-blue-600"
              />
              <span className="text-xs text-gray-600 whitespace-nowrap w-12">{daysBack} дн.</span>
            </div>
          )}

          {isRunning && (
            <div className="flex items-center gap-2">
              <div className="w-40 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.round(taskProgress * 100)}%` }}
                />
              </div>
              <span className="text-xs text-gray-500 whitespace-nowrap">
                {Math.round(taskProgress * 100)}% · {taskMessage}
              </span>
            </div>
          )}
          {taskStatus === "error" && (
            <div className="flex items-center gap-1.5 text-red-600 text-xs">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>{taskError}</span>
            </div>
          )}
          <button
            onClick={handleRun}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <RefreshCw className="w-3.5 h-3.5" />
            }
            {topics.length === 0 ? "Построить карту" : "Обновить"}
          </button>
        </div>
      </div>

      {/* Карта — stopPropagation чтобы клики не закрывали сайдбар через <main onClick> */}
      <div
        className="flex-1 relative overflow-hidden bg-gray-50"
        onClick={(e) => e.stopPropagation()}
      >
        {isLoadingTopics ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : topics.length === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-center px-8">
            <div className="w-16 h-16 rounded-full bg-blue-50 flex items-center justify-center">
              <Map className="w-8 h-8 text-blue-300" />
            </div>
            <div>
              <p className="text-gray-700 font-medium">Карта ещё не построена</p>
              <p className="text-sm text-gray-400 mt-1">
                Нажмите «Построить карту» — BERTopic автоматически
                <br />найдёт темы в ваших статьях и разместит их на карте
              </p>
            </div>
            <button
              onClick={handleRun}
              disabled={isRunning}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isRunning ? "Строим карту..." : "Построить карту"}
            </button>
          </div>
        ) : (
          <BubbleMap
            topics={topics}
            selectedId={selectedTopicId}
            onSelect={handleSelectTopic}
          />
        )}
      </div>
    </div>
  );
}
