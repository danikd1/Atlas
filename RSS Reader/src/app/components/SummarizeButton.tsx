import { Lightbulb, Loader2 } from "lucide-react";
import { useState } from "react";
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
    try {
      const result = await api.summarizeArticle(articleId);
      if (result.ai_summary) {
        onLoad(result.ai_summary);
      }
    } catch (err) {
      console.error("Ошибка суммаризации:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const iconClass = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";
  const btnClass = size === "sm" ? "p-1 rounded transition-colors" : "p-1.5 rounded-md transition-colors";

  const isActive = hasSummary && summaryVisible;
  const label = isActive ? "Скрыть резюме" : "Показать AI-резюме";

  return (
    <div className="relative group/summarize flex-shrink-0">
      <button
        onClick={handleClick}
        className={`${btnClass} rounded-lg transition-colors ${
          isLoading
            ? "text-amber-400 cursor-wait hover:bg-gray-200"
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

      {/* Tooltip */}
      <div className="pointer-events-none absolute bottom-full right-0 mb-2 hidden group-hover/summarize:block z-50">
        <div className="bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
          {label}
        </div>
        <div className="absolute top-full right-2.5 border-4 border-transparent border-t-gray-800" />
      </div>
    </div>
  );
}
