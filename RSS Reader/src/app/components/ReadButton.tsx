import { useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../lib/api";

interface ReadButtonProps {
  link: string;
  isRead: boolean;
  onToggle: (isRead: boolean) => void;
}

export function ReadButton({ link, isRead, onToggle }: ReadButtonProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isLoading) return;

    const newIsRead = !isRead;
    onToggle(newIsRead);
    setIsLoading(true);
    try {
      if (newIsRead) {
        await api.markArticleRead(link);
      } else {
        await api.unmarkArticleRead(link);
      }
    } catch (err) {
      console.error("Ошибка смены статуса прочтения:", err);
      onToggle(isRead); // откат
    } finally {
      setIsLoading(false);
    }
  };

  const label = isRead ? "Отметить как непрочитанное" : "Отметить как прочитанное";

  return (
    <div className="relative group/read flex-shrink-0">
      <button
        onClick={handleClick}
        aria-label={label}
        className={`w-2.5 h-2.5 rounded-full flex items-center justify-center transition-all hover:scale-125 ${
          isRead
            ? "border-2 border-gray-300 hover:border-blue-400 bg-transparent"
            : "bg-blue-500 hover:bg-blue-400"
        }`}
      >
        {isLoading && (
          <Loader2 className="w-2 h-2 animate-spin text-blue-400" />
        )}
      </button>

      {/* Tooltip */}
      <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/read:block z-50">
        <div className="bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
          {label}
        </div>
      </div>
    </div>
  );
}
