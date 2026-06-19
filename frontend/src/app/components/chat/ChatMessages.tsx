import { Children, isValidElement, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { ExternalLink, Link2, Bot } from "lucide-react";
import type { ChatDisplayMessage } from "../../lib/chatStorage";

const LOADING_STEPS = [
  "Ищу в базе знаний...",
  "Оцениваю релевантность...",
  "Формулирую ответ...",
];

const EXAMPLE_QUESTIONS = [
  "Что нового по теме кибербезопасности?",
  "Найди статьи про микросервисы",
  "Расскажи про контейнеризацию",
  "Какие статьи о машинном обучении?",
];

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    return new Date(dateStr).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

// Убирает мусор из ответа GigaChat:
// - цитаты [Заголовок] без ссылки
// - [Источник](url) — избыточно, заголовок уже является ссылкой
function cleanAnswer(text: string): string {
  return text
    .replace(/\s*\[Источник\]\([^)]+\)/gi, "")       // [Источник](url)
    .replace(/\s*\[[^\]\n]+\](?!\s*\()/g, "")         // [цитаты] без url
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Делает голые URL кликабельными
function autoLinkUrls(text: string): string {
  return text.replace(/(?<!\]\()https?:\/\/[^\s)>"[\]]+/g, (url) => `[${url}](${url})`);
}

// "Опубликована: 2026-04-13" → "13 апр. 2026 г."
function formatDatesInText(text: string): string {
  return text.replace(
    /Опубликован[аоo]?:?\s*(\d{4}-\d{2}-\d{2})/gi,
    (_, d) => formatDate(d)
  );
}

// **«Title»**\n21 апр. 2026 г. → **«Title»** — 21 апр. 2026 г.
function mergeDateIntoTitle(text: string): string {
  return text.replace(
    /(\*\*[^\n*]+\*\*)\n+[ \t]*(\d{1,2}\s+[а-яА-ЯёЁ.]+\s+\d{4}(?:\s+г\.)?)/g,
    "$1 — $2"
  );
}

// Добавляет серый бейдж `domain` в конец последней строки блока (описание)
function appendSourceBadges(
  text: string,
  sources: NonNullable<ChatDisplayMessage["sources"]>
): string {
  if (!sources.length) return text;
  const lines = text.split("\n");

  for (const s of sources) {
    if (!s.title || !s.link) continue;
    const domain = extractDomain(s.link);
    const badge = ` [\`${domain}\`](${s.link})`;
    const e = s.title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const titleRe = new RegExp(`\\*\\*[«""]?${e}[»""]?\\*\\*`);

    const titleIdx = lines.findIndex((l) => titleRe.test(l));
    if (titleIdx === -1) continue;

    // Ищем последнюю строку этого блока (до пустой строки или нового пункта списка)
    let lastIdx = titleIdx;
    for (let i = titleIdx + 1; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      if (trimmed === "") break;
      if (/^[-*#]|\d+\./.test(trimmed)) break;
      lastIdx = i;
    }

    if (!lines[lastIdx].includes(domain)) {
      lines[lastIdx] = lines[lastIdx].trimEnd() + badge;
    }
  }

  return lines.join("\n");
}

// **Заголовок** → **[Заголовок](url)**, включая **"Заголовок"** с кавычками
function linkifyTitles(text: string, sources: NonNullable<ChatDisplayMessage["sources"]>): string {
  if (!sources.length) return text;
  let result = text;
  for (const s of sources) {
    if (!s.title || !s.link) continue;
    const e = s.title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    result = result
      .replace(new RegExp(`\\*\\*(${e})\\*\\*(?!\\s*\\()`, "g"), `**[$1](${s.link})**`)
      .replace(new RegExp(`\\*\\*"(${e})"\\*\\*(?!\\s*\\()`, "g"), `**[$1](${s.link})**`)
      .replace(new RegExp(`\\*\\*«(${e})»\\*\\*(?!\\s*\\()`, "g"), `**[«$1»](${s.link})**`);
  }
  return result;
}

// Тултип при наведении на серый бейдж домена
function BadgeTooltip({
  href,
  children,
  sources,
  onOpenArticle,
}: {
  href: string;
  children: React.ReactNode;
  sources: NonNullable<ChatDisplayMessage["sources"]>;
  onOpenArticle?: (id: number) => void;
}) {
  const [visible, setVisible] = useState(false);
  const source = sources.find((s) => s.link === href);
  const domain = extractDomain(href);

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <a href={href} target="_blank" rel="noopener noreferrer" className="no-underline">
        {children}
      </a>
      {visible && (
        <div className="not-prose absolute top-full left-0 mt-2 z-50 w-72 bg-white rounded-xl shadow-xl border border-gray-100 p-3">
          <div className="flex items-center gap-2 mb-1">
            <img
              src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
              className="w-4 h-4 rounded-sm flex-shrink-0"
              alt=""
            />
            <span className="text-xs font-semibold text-gray-500">{domain}</span>
          </div>
          {source?.title && (
            <p className="text-sm font-medium text-gray-900 leading-snug mt-0 mb-1 line-clamp-2">
              {source.title}
            </p>
          )}
          {source?.snippet && (
            <p className="text-xs text-gray-500 leading-relaxed mt-0 mb-2 line-clamp-3">
              {source.snippet}
            </p>
          )}
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100">
            {source?.article_id && onOpenArticle && (
              <button
                onClick={() => { setVisible(false); onOpenArticle(source.article_id!); }}
                className="flex-1 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 px-2.5 py-1.5 rounded-lg transition-colors text-center"
              >
                Читать в Atlas
              </button>
            )}
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-xs font-medium text-gray-600 hover:text-gray-900 border border-gray-200 hover:border-gray-300 px-2.5 py-1.5 rounded-lg transition-colors text-center"
            >
              ↗ Сайт
            </a>
          </div>
        </div>
      )}
    </span>
  );
}

interface ChatMessagesProps {
  messages: ChatDisplayMessage[];
  isLoading: boolean;
  onExampleClick?: (question: string) => void;
  onOpenArticle?: (id: number) => void;
}

function LoadingBubble() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % LOADING_STEPS.length), 2000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Bot className="w-4 h-4 text-blue-600" />
      </div>
      <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <p className="text-sm text-gray-400 animate-pulse">{LOADING_STEPS[step]}</p>
      </div>
    </div>
  );
}

function SourcesList({
  sources,
  onOpenArticle,
}: {
  sources: NonNullable<ChatDisplayMessage["sources"]>;
  onOpenArticle?: (id: number) => void;
}) {
  if (sources.length === 0) return null;
  return (
    <div className="mt-4 pt-3 border-t border-gray-100">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
        <Link2 className="w-3.5 h-3.5" />
        Связанные статьи
      </div>
      <div className="space-y-1.5">
        {sources.map((s, i) => (
          <div key={s.link} className="flex items-start gap-2.5 py-1.5 group">
            <span className="text-xs text-gray-300 flex-shrink-0 w-4 pt-0.5 text-right">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                {/* Заголовок — открывает панель Atlas если есть article_id */}
                {s.article_id && onOpenArticle ? (
                  <button
                    onClick={() => onOpenArticle(s.article_id!)}
                    className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline leading-snug text-left"
                  >
                    {s.title || extractDomain(s.link)}
                  </button>
                ) : (
                  <a
                    href={s.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline leading-snug"
                  >
                    {s.title || extractDomain(s.link)}
                  </a>
                )}
                <span className="text-xs text-gray-400 whitespace-nowrap">
                  {extractDomain(s.link)}
                  {s.published_at && <> · {formatDate(s.published_at)}</>}
                </span>
                {/* Иконка — всегда внешняя ссылка */}
                <a
                  href={s.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="w-3 h-3 text-gray-300 hover:text-blue-400 flex-shrink-0" />
                </a>
              </div>
              {s.snippet && (
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  {s.snippet}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatMessages({ messages, isLoading, onExampleClick, onOpenArticle }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-4">
          <Bot className="w-8 h-8 text-blue-600" />
        </div>
        <h2 className="text-xl font-semibold text-gray-800 mb-2">Atlas Chat</h2>
        <p className="text-gray-500 text-sm mb-8 max-w-xs">
          Задай вопрос — отвечу по статьям из базы знаний Atlas
        </p>
        <div className="grid grid-cols-2 gap-2 max-w-md w-full">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => onExampleClick?.(q)}
              className="text-left p-3 rounded-xl border border-gray-200 text-sm text-gray-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
      {messages.map((msg, i) => (
        <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} items-start gap-3`}>
          {msg.role === "assistant" && (
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Bot className="w-4 h-4 text-blue-600" />
            </div>
          )}

          <div
            className={`rounded-2xl px-4 py-3 shadow-sm ${
              msg.role === "user"
                ? "max-w-[75%] bg-blue-600 text-white rounded-tr-sm"
                : "max-w-[85%] bg-white border border-gray-200 text-gray-800 rounded-tl-sm"
            }`}
          >
            {msg.role === "user" ? (
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            ) : (() => {
              const sources = msg.sources ?? [];
              const processedText = appendSourceBadges(
                mergeDateIntoTitle(formatDatesInText(autoLinkUrls(cleanAnswer(msg.content)))),
                sources
              );

              // Ссылки, уже встроенные в текст GigaChat — исключаем из списка
              const linkedUrls = new Set(
                (processedText.match(/\]\((https?:\/\/[^)]+)\)/g) ?? []).map((m) => m.slice(2, -1))
              );
              const sixMonthsAgo = new Date();
              sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);

              const filteredSources = sources
                .filter((s) => {
                  if (!s.link || linkedUrls.has(s.link)) return false;
                  if (s.published_at && new Date(s.published_at) < sixMonthsAgo) return false;
                  return true;
                })
                .slice(0, 5);

              return (
                <div>
                  {/* Prose-блок только для текста GigaChat */}
                  {/* Кастомный рендер ссылок: бейдж-ссылки (a > code) → тултип */}
                  {(() => {
                    const markdownComponents = {
                      a({ href, children }: { href?: string; children?: React.ReactNode }) {
                        const isBadge = Children.toArray(children).some(
                          (c) => isValidElement(c) && c.type === "code"
                        );
                        if (isBadge && href) {
                          return (
                            <BadgeTooltip href={href} sources={sources} onOpenArticle={onOpenArticle}>
                              {children}
                            </BadgeTooltip>
                          );
                        }
                        return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                      },
                    };
                    return (
                  <div
                    className="
                      text-sm prose prose-sm max-w-none
                      prose-p:my-1.5 prose-p:leading-relaxed
                      prose-ul:my-2 prose-ul:pl-4
                      prose-ol:my-2 prose-ol:pl-4
                      prose-li:my-1.5 prose-li:leading-relaxed
                      prose-strong:font-semibold prose-strong:text-gray-900
                      prose-headings:font-semibold prose-headings:text-gray-900 prose-headings:mt-3 prose-headings:mb-1
                      prose-code:text-gray-500 prose-code:bg-gray-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-normal
                      prose-a:text-blue-600 prose-a:no-underline prose-a:font-medium
                      prose-hr:my-3 prose-hr:border-gray-100
                      [&_code::before]:content-none [&_code::after]:content-none
                    "
                  >
                    <Markdown components={markdownComponents}>{processedText}</Markdown>
                  </div>
                    );
                  })()}
                  {/* SourcesList вне prose — своя стилизация, без hover:underline на весь блок */}
                  {filteredSources.length > 0 && <SourcesList sources={filteredSources} onOpenArticle={onOpenArticle} />}
                </div>
              );
            })()}
          </div>
        </div>
      ))}

      {isLoading && (
        <div className="flex justify-start">
          <LoadingBubble />
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
