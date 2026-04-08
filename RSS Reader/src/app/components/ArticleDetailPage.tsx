import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { ArrowLeft, ExternalLink, Clock, User } from "lucide-react";
import { RSSArticle } from "../types";
import { getArticleById, markArticleAsRead } from "../lib/storage";
import { format } from "date-fns";

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [article, setArticle] = useState<RSSArticle | null>(null);

  useEffect(() => {
    if (!id) return;

    const foundArticle = getArticleById(id);
    if (foundArticle) {
      setArticle(foundArticle);
      // Mark as read when viewing
      if (!foundArticle.read) {
        markArticleAsRead(id);
      }
    } else {
      navigate("/");
    }
  }, [id, navigate]);

  if (!article) {
    return (
      <div className="max-w-4xl mx-auto text-center py-12">
        <p className="text-gray-500">Загрузка статьи...</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <Link
        to="/articles"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Назад к статьям
      </Link>

      <article className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
        <div className="mb-4">
          <span className="text-sm font-medium text-blue-600 bg-blue-50 px-3 py-1 rounded">
            {article.feedTitle}
          </span>
        </div>

        <h1 className="text-3xl font-semibold text-gray-900 mb-4">
          {article.title}
        </h1>

        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600 mb-6 pb-6 border-b border-gray-200">
          {article.author && (
            <div className="flex items-center gap-1">
              <User className="w-4 h-4" />
              {article.author}
            </div>
          )}
          <div className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            {format(new Date(article.pubDate), "MMMM d, yyyy 'at' h:mm a")}
          </div>
          <a
            href={article.link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-blue-600 hover:text-blue-700"
          >
            <ExternalLink className="w-4 h-4" />
            Оригинал
          </a>
        </div>

        {article.content ? (
          <div 
            className="prose prose-gray max-w-none"
            dangerouslySetInnerHTML={{ __html: article.content }}
          />
        ) : (
          <div className="text-gray-700">
            <p>{article.description}</p>
            <div className="mt-6 p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-600">
                Full content not available. 
                <a
                  href={article.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 ml-1"
                >
                  Read the full article on the original site →
                </a>
              </p>
            </div>
          </div>
        )}
      </article>
    </div>
  );
}