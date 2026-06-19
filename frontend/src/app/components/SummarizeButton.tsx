import { Lightbulb, Loader2 } from "lucide-react";
import { useState, useEffect } from "react";
import { api } from "../lib/api";

interface SummarizeButtonProps {
  articleId: number;
  /** Резюме уже загружено (не нужен запрос к API) */
  hasSummary: boolean;
  /** Панель резюме сейчас видна */
  summaryVisible: boolean;
  /** Вызывается когда резюме загружено впервые — передаёт текст наверх */
  onLoad: (text: string) => void;
  /** Переключает видимость уже загруженного резюме */
  onToggle: () => void;
  size?: "sm" | "md";
  strokeWidth?: number;
}

export function SummarizeButton({
  articleId,
  hasSummary,
  summaryVisible,
  onLoad,
  onToggle,
  size = "md",
  strokeWidth = 2,
}: SummarizeButtonProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Автоматически скрываем сообщение об ошибке через 4 секунды
  useEffect(() => {
    if (!errorMsg) return;
    const t = setTimeout(() => setErrorMsg(null), 4000);
    return () => clearTimeout(t);
  }, [errorMsg]);

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Уже загружено — просто переключить видимость
    if (hasSummary) {
      onToggle();
      return;
    }

    if (isLoading) return;
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const result = await api.summarizeArticle(articleId);
      if (result.ai_summary) {
        onLoad(result.ai_summary);
      } else {
        // Бэкенд вернул null — показываем причину пользователю
        setErrorMsg(result.error ?? "Не удалось создать резюме");
      }
    } catch (err) {
      console.error("Ошибка суммаризации:", err);
      setErrorMsg("Ошибка соединения");
    } finally {
      setIsLoading(false);
    }
  };

  const iconClass = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";
  const btnClass = size === "sm" ? "p-1 rounded transition-colors" : "p-1.5 rounded-md transition-colors";

  const isActive = hasSummary && summaryVisible;
  const hasError = !!errorMsg;
  const label = hasError ? errorMsg! : isActive ? "Скрыть резюме" : "Показать AI-резюме";

  return (
    <div className="relative group/summarize flex-shrink-0">
      <button
        onClick={handleClick}
        className={`${btnClass} rounded-lg transition-colors ${
          isLoading
            ? "text-amber-400 cursor-wait hover:bg-gray-200"
            : hasError
              ? "text-red-400 hover:bg-gray-200"
              : isActive
                ? "text-amber-500 hover:text-amber-600 hover:bg-gray-200"
                : "text-gray-300 hover:text-amber-400 hover:bg-gray-200"
        }`}
      >
        {isLoading
          ? <Loader2 className={`${iconClass} animate-spin`} strokeWidth={strokeWidth} />
          : <Lightbulb className={`${iconClass} ${isActive ? "fill-current" : ""}`} strokeWidth={strokeWidth} />
        }
      </button>

      {/* Tooltip — ошибка показывается сразу (без hover), остальное по hover */}
      <div className={`pointer-events-none absolute bottom-full right-0 mb-2 z-50 ${hasError ? "block" : "hidden group-hover/summarize:block"}`}>
        <div className={`text-white text-xs rounded px-2 py-1 whitespace-nowrap ${hasError ? "bg-red-600" : "bg-gray-800"}`}>
          {label}
        </div>
        <div className={`absolute top-full right-2.5 border-4 border-transparent ${hasError ? "border-t-red-600" : "border-t-gray-800"}`} />
      </div>
    </div>
  );
}
