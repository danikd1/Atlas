import { useState } from "react";
import { Globe, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { translationCache } from "../lib/translationCache";

export interface TranslationResult {
  title: string | null;
  summary: string | null;
  full_text: string | null;
}

interface TranslateButtonProps {
  articleId: number;
  /** Есть ли уже перевод в кэше */
  isTranslated: boolean;
  /** Сейчас показывается перевод (true) или оригинал (false) */
  isShowingTranslation: boolean;
  onTranslated: (result: TranslationResult) => void;
  onToggle: (show: boolean) => void;
}

export function TranslateButton({
  articleId,
  isTranslated,
  isShowingTranslation,
  onTranslated,
  onToggle,
}: TranslateButtonProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (isLoading) return;

    if (!isTranslated) {
      // Нет перевода — запускаем
      setIsLoading(true);
      try {
        const result = await api.translateArticle(articleId);
        translationCache.set(articleId, result);
        onTranslated(result);
      } catch (err) {
        console.error("Ошибка перевода:", err);
      } finally {
        setIsLoading(false);
      }
    } else {
      // Перевод есть — переключаем язык
      onToggle(!isShowingTranslation);
    }
  };

  // ── Вид кнопки зависит от состояния ──────────────────────────
  // idle (нет перевода):      🌐 globe серый
  // loading:                  спиннер
  // translated + showing RU:  "EN" — клик вернёт оригинал
  // translated + showing EN:  "RU" — клик покажет перевод

  let content: React.ReactNode;
  let label: string;
  let colorClass: string;

  if (isLoading) {
    content = <Loader2 className="w-4 h-4 animate-spin" />;
    label = "Переводим...";
    colorClass = "text-blue-400 cursor-wait border-gray-300";
  } else if (!isTranslated) {
    content = <Globe className="w-4 h-4" strokeWidth={2.5} />;
    label = "Перевести на русский";
    colorClass = "text-gray-500 hover:text-blue-500 border-gray-300 hover:border-blue-400";
  } else if (isShowingTranslation) {
    content = <span className="text-xs font-bold tracking-wide">EN</span>;
    label = "Показать оригинал";
    colorClass = "text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-500";
  } else {
    content = <span className="text-xs font-bold tracking-wide">RU</span>;
    label = "Показать перевод";
    colorClass = "text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-500";
  }

  return (
    <div className="relative group/translate flex-shrink-0">
      <button
        onClick={handleClick}
        aria-label={label}
        className={`w-8 h-8 rounded-lg border transition-colors flex items-center justify-center ${colorClass}`}
      >
        {content}
      </button>

      <div className="pointer-events-none absolute bottom-full right-0 mb-2 hidden group-hover/translate:block z-50">
        <div className="bg-gray-800 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
          {label}
        </div>
        <div className="absolute top-full right-2.5 border-4 border-transparent border-t-gray-800" />
      </div>
    </div>
  );
}
