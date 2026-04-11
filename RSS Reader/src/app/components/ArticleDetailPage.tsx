import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import { ArrowLeft, ExternalLink, Clock, Loader2, AlertCircle } from "lucide-react";
import { api, ApiArticleDetail } from "../lib/api";
import { StarButton } from "./StarButton";
import { TranslateButton, TranslationResult } from "./TranslateButton";
import { translationCache } from "../lib/translationCache";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale/ru";

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [article, setArticle] = useState<ApiArticleDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // Перевод: берём из кэша или получаем по запросу
  const [translation, setTranslation] = useState<TranslationResult | null>(null);
  const [showingTranslation, setShowingTranslation] = useState(false);

  const isTranslated = translation !== null;

  // Проверка языка: кириллица в заголовке или summary → статья русская
  const hasCyrillic = (text: string | null | undefined) =>
    text ? /[а-яёА-ЯЁ]/.test(text) : false;
  const isRussian = !isTranslated && (hasCyrillic(article?.title) || hasCyrillic(article?.summary));

  // Отображаемый контент — перевод или оригинал
  const displayTitle = showingTranslation && translation ? (translation.title ?? article?.title) : article?.title;
  const displaySummary = showingTranslation && translation ? (translation.summary ?? article?.summary) : article?.summary;
  const displayFullText = showingTranslation && translation ? (translation.full_text ?? article?.full_text) : article?.full_text;

  useEffect(() => {
    if (!id) return;
    const articleId = parseInt(id);
    // Проверяем кэш — вдруг уже переводили эту статью
    const cached = translationCache.get(articleId);
    setTranslation(cached);
    setShowingTranslation(cached !== null);
    loadArticle(articleId);
  }, [id]);

  const loadArticle = async (articleId: number) => {
    setIsLoading(true);
    setNotFound(false);
    try {
      const data = await api.getArticleById(articleId);
      setArticle(data);

      if (!data.is_read) {
        try {
          await api.markArticleRead(data.link);
          window.dispatchEvent(new CustomEvent("feeds-updated"));
        } catch (e) {
          console.error("Ошибка пометки прочитанной:", e);
        }
      }
    } catch (e) {
      setNotFound(true);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "";
    try {
      return formatDistanceToNow(new Date(dateStr), { addSuffix: true, locale: ru });
    } catch {
      return "";
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Назад
        </button>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="flex items-center justify-center py-16 text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin mr-3" />
            <span>Загружаем статью...</span>
          </div>
        </div>
      </div>
    );
  }

  if (notFound || !article) {
    return (
      <div className="max-w-3xl mx-auto" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Назад
        </button>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center py-16">
          <AlertCircle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">Статья не найдена</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto" onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Назад
      </button>

      <article className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        {article.source && (
          <div className="mb-4">
            <span className="text-sm font-medium text-blue-600 bg-blue-50 px-3 py-1 rounded">
              {article.source}
            </span>
          </div>
        )}

        <h1 className="text-2xl font-semibold text-gray-900 mb-4 leading-tight">
          {displayTitle ?? "Без заголовка"}
        </h1>

        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 mb-6 pb-6 border-b border-gray-200">
          {article.published_at && (
            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {formatDate(article.published_at)}
            </div>
          )}
          <div className="flex items-center gap-3 ml-auto">
            {!isRussian && (
              <TranslateButton
                articleId={article.id}
                isTranslated={isTranslated}
                isShowingTranslation={showingTranslation}
                onTranslated={(result) => {
                  setTranslation(result);
                  setShowingTranslation(true);
                }}
                onToggle={(show) => setShowingTranslation(show)}
              />
            )}
            <StarButton
              link={article.link}
              isSaved={article.is_saved}
              onToggle={(saved) => setArticle((prev) => prev ? { ...prev, is_saved: saved } : prev)}
              size="md"
            />
            <a
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-blue-600 hover:text-blue-700"
            >
              <ExternalLink className="w-4 h-4" />
              Открыть оригинал
            </a>
          </div>
        </div>

        {displayFullText ? (
          <div
            className="prose prose-gray max-w-none prose-a:text-blue-600 prose-img:rounded-lg"
            dangerouslySetInnerHTML={{ __html: displayFullText }}
          />
        ) : (
          <div className="text-gray-700">
            {displaySummary && <p className="leading-relaxed">{displaySummary}</p>}
            <div className="mt-6 p-4 bg-gray-50 rounded-md border border-gray-200">
              <p className="text-sm text-gray-500">
                Полный текст недоступен.{" "}
                <a
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700"
                >
                  Читать на оригинальном сайте →
                </a>
              </p>
            </div>
          </div>
        )}
      </article>
    </div>
  );
}
