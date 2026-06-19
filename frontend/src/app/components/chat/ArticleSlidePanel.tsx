import { useEffect, useState } from "react";
import { X, ExternalLink, Clock, Loader2 } from "lucide-react";
import { api, type ApiArticleDetail } from "../../lib/api";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// Убираем первый <h1> из HTML — он дублирует заголовок
function stripFirstH1(html: string): string {
  return html.replace(/<h1[^>]*>.*?<\/h1>/is, "");
}

interface ArticleSlidePanelProps {
  articleId: number;
  onClose: () => void;
}

export function ArticleSlidePanel({ articleId, onClose }: ArticleSlidePanelProps) {
  const [article, setArticle] = useState<ApiArticleDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Запускаем анимацию появления
    const t = setTimeout(() => setVisible(true), 10);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    setLoading(true);
    setArticle(null);
    api.getArticleById(articleId)
      .then(setArticle)
      .catch(() => setArticle(null))
      .finally(() => setLoading(false));
  }, [articleId]);

  const handleClose = () => {
    setVisible(false);
    setTimeout(onClose, 300);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/20 z-40 transition-opacity duration-300 ${
          visible ? "opacity-100" : "opacity-0"
        }`}
        onClick={handleClose}
      />

      {/* Панель */}
      <div
        className={`fixed right-0 top-0 h-full w-[620px] max-w-[90vw] bg-white shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${
          visible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Шапка */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 flex-shrink-0">
          <button
            onClick={handleClose}
            className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            title="Закрыть"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>

          {article && (
            <a
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              Открыть оригинал
            </a>
          )}
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 animate-spin text-gray-300" />
            </div>
          ) : !article ? (
            <p className="text-sm text-gray-400 text-center mt-10">Статья не найдена</p>
          ) : (
            <article>
              {article.source && (
                <span className="inline-block text-xs font-medium text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md mb-4">
                  {article.source}
                </span>
              )}

              <h1 className="text-xl font-semibold text-gray-900 leading-snug mb-3">
                {article.title ?? "Без заголовка"}
              </h1>

              {article.published_at && (
                <div className="flex items-center gap-1.5 text-sm text-gray-400 mb-6 pb-6 border-b border-gray-100">
                  <Clock className="w-3.5 h-3.5" />
                  {formatDate(article.published_at)}
                </div>
              )}

              {article.full_text ? (
                <div
                  className="prose prose-sm max-w-none text-gray-700 prose-headings:text-gray-900 prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline prose-img:rounded-lg"
                  dangerouslySetInnerHTML={{ __html: stripFirstH1(article.full_text) }}
                />
              ) : article.summary ? (
                <p className="text-sm text-gray-600 leading-relaxed">{article.summary}</p>
              ) : (
                <p className="text-sm text-gray-400">Текст статьи недоступен</p>
              )}
            </article>
          )}
        </div>
      </div>
    </>
  );
}
