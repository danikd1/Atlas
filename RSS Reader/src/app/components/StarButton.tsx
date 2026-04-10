import { Star } from "lucide-react";
import { api } from "../lib/api";

interface StarButtonProps {
  link: string;
  isSaved: boolean;
  onToggle: (saved: boolean) => void;
  size?: "sm" | "md";
}

export function StarButton({ link, isSaved, onToggle, size = "md" }: StarButtonProps) {
  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      if (isSaved) {
        await api.unbookmarkArticle(link);
        onToggle(false);
      } else {
        await api.bookmarkArticle(link);
        onToggle(true);
      }
    } catch (err) {
      console.error("Ошибка закладки:", err);
    }
  };

  const iconClass = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";
  const btnClass = size === "sm"
    ? "p-1 rounded transition-colors"
    : "p-1.5 rounded-md transition-colors";

  const label = isSaved ? "Убрать из сохраненного" : "Добавить пост в сохраненное";

  return (
    <div className="relative group/star flex-shrink-0">
      <button
        onClick={handleClick}
        className={`${btnClass} ${
          isSaved
            ? "text-yellow-500 hover:text-yellow-600"
            : "text-gray-300 hover:text-yellow-400"
        }`}
      >
        <Star className={`${iconClass} ${isSaved ? "fill-current" : ""}`} />
      </button>

      {/* Tooltip */}
      <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/star:block z-50">
        <div className="bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
          {label}
        </div>
      </div>
    </div>
  );
}
