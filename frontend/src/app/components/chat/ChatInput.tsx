import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

const MAX_LENGTH = 2000;

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isLoading || trimmed.length > MAX_LENGTH) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const tooLong = value.length > MAX_LENGTH;

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      {tooLong && (
        <p className="text-xs text-red-500 mb-2">
          Сообщение слишком длинное. Максимум {MAX_LENGTH} символов (сейчас {value.length}).
        </p>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Задайте вопрос по базе знаний Atlas..."
          rows={1}
          className={`flex-1 resize-none rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400 transition-colors ${
            tooLong ? "border-red-300 focus:ring-red-400" : "border-gray-300"
          }`}
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !value.trim() || tooLong}
          className="flex-shrink-0 p-2.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title="Отправить (Enter)"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
      <p className="text-xs text-gray-400 mt-1.5">Enter — отправить, Shift+Enter — новая строка</p>
    </div>
  );
}
