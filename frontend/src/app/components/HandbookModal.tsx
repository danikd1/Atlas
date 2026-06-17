import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { ExternalLink, X, Rss, Sparkles, Map, MessageSquare, BookText, Layers, MousePointerClick, RefreshCw } from "lucide-react";
import atlasLogo from "../assets/atlas-logo2.png";

const STORAGE_KEY = "atlas_handbook_done_v1";

const PAGE_TITLES = [
  "Добро пожаловать в Atlas!",
  "Ленты и источники",
  "Вопрос-ответ и Дайджест",
  "Карта тем",
  "Подключите GigaChat",
];

interface HandbookModalProps {
  /** Показывать крестик (повторный вызов из хедера) */
  closable?: boolean;
  onClose: () => void;
  onOpenProfile: () => void;
}

// ── Страница 1 ────────────────────────────────────────────────────

function Page1() {
  const cards = [
    { icon: <Rss className="w-6 h-6" />, label: "Автосбор статей", iconColor: "text-blue-500", bg: "bg-blue-50" },
    { icon: <Sparkles className="w-6 h-6" />, label: "ИИ-инструменты для работы", iconColor: "text-purple-500", bg: "bg-purple-50" },
    { icon: <Map className="w-6 h-6" />, label: "Карта тем по твоим подпискам", iconColor: "text-emerald-500", bg: "bg-emerald-50" },
  ];

  return (
    <div className="space-y-4">
      <p className="text-gray-600 leading-relaxed" style={{ fontSize: "15px" }}>
        <span className="font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          ATLAS
        </span>{" "}
        — твой личный помощник для работы со статьями в области
        информационных технологий. Подпишись на нужные источники, а мы
        возьмём на себя всё остальное.
      </p>
      <p className="text-gray-600 leading-relaxed" style={{ fontSize: "15px" }}>
        Больше не нужно вручную просматривать десятки сайтов — Atlas сам
        соберёт статьи, поможет структурировать знания из непрерывного
        потока новостей, разобраться в теме и покажет, что сейчас в тренде
        среди твоих подписок.
      </p>

      <div className="grid grid-cols-3 gap-3 pt-1">
        {cards.map(({ icon, label, iconColor, bg }, i) => (
          <motion.div
            key={label}
            className={`flex flex-col items-center gap-2.5 p-4 rounded-xl text-center ${bg}`}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.15 + i * 0.1, ease: "easeOut" }}
          >
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${bg} ${iconColor}`}>
              {icon}
            </div>
            <span className="text-xs text-gray-500 leading-snug">{label}</span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

// ── Страница 2 ────────────────────────────────────────────────────

function Page2() {
  const steps = [
    {
      step: "1",
      title: "Установите RSSHub Radar",
      desc: (
        <>
          Расширение для Chrome — помогает находить RSS-ленты на любом сайте одним кликом.{" "}
          <a
            href="https://chromewebstore.google.com/detail/kefjpfngnndepjbopdmoebkipbgkggaa?utm_source=item-share-cb"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline inline-flex items-center gap-0.5"
          >
            Скачать из Chrome Web Store
            <ExternalLink className="w-3 h-3" />
          </a>
        </>
      ),
    },
    { step: "2", title: "Перейдите в «Мои источники»", desc: "Кнопка в верхней навигации" },
    { step: "3", title: "Добавьте RSS-ленту", desc: "Вставьте URL или выберите из каталога готовых источников" },
    { step: "4", title: "Статьи обновляются автоматически", desc: "Atlas проверяет ленты по расписанию и добавляет новые публикации" },
  ];

  return (
    <div className="space-y-4">
      <motion.p
        className="text-gray-600 leading-relaxed"
        style={{ fontSize: "15px" }}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        Atlas автоматически собирает статьи из <b>RSS-лент</b>. Добавьте
        интересующие вас источники — блоги, новостные сайты, технические издания.
      </motion.p>
      <div className="space-y-3">
        {steps.map(({ step, title, desc }, i) => (
          <motion.div
            key={step}
            className="flex gap-3 items-start"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 + i * 0.1, ease: "easeOut" }}
          >
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center font-semibold">
              {step}
            </span>
            <div>
              <p className="text-sm font-medium text-gray-800">{title}</p>
              <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
            </div>
          </motion.div>
        ))}
      </div>
      <motion.p
        className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.55, ease: "easeOut" }}
      >
        Используйте папки для группировки источников с помощью drag&amp;drop
      </motion.p>
    </div>
  );
}

// ── Страница 3 ────────────────────────────────────────────────────

function Page3() {
  const qaExamples = [
    "О чём вообще пишут в этой ленте?",
    "Какие AI-инструменты для разработчиков упоминались на этой неделе?",
    "Есть ли статьи про оптимизацию PostgreSQL?",
    "Какие подходы к микросервисам обсуждались?",
  ];

  return (
    <div className="space-y-4">
      <motion.p
        className="text-gray-600 leading-relaxed"
        style={{ fontSize: "15px" }}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        Подпишись на любую ленту — в панели статей появятся два инструмента для
        глубокой работы с контентом.
      </motion.p>
      <div className="space-y-3">
        {/* QA */}
        <motion.div
          className="p-3 border border-blue-100 bg-blue-50 rounded-xl"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15, ease: "easeOut" }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <MessageSquare className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
            <p className="text-sm font-semibold text-blue-800">Вопрос-ответ (QA)</p>
          </div>
          <p className="text-xs text-blue-700 leading-relaxed mb-2">
            QA читал каждую статью в открытой ленте — можно спросить про конкретный материал или задать общий вопрос по всей теме.
          </p>
          <div className="space-y-1">
            {qaExamples.map((ex, i) => (
              <motion.p
                key={i}
                className="text-xs text-blue-600 bg-white/70 rounded-lg px-2 py-1"
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25, delay: 0.3 + i * 0.08, ease: "easeOut" }}
              >
                «{ex}»
              </motion.p>
            ))}
          </div>
        </motion.div>

        {/* Дайджест */}
        <motion.div
          className="p-3 border border-purple-100 bg-purple-50 rounded-xl"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.7, ease: "easeOut" }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <BookText className="w-3.5 h-3.5 text-purple-600 flex-shrink-0" />
            <p className="text-sm font-semibold text-purple-800">Дайджест</p>
          </div>
          <p className="text-xs text-purple-700 leading-relaxed">
            Каждый день выходят десятки статей — читать все нереально. AI анализирует каждую статью и собирает общую картину: тренды, популярные инструменты и ключевые идеи — без воды.
          </p>
        </motion.div>
      </div>
      <motion.p
        className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.9, ease: "easeOut" }}
      >
        Рядом с каждым инструментом есть кнопка <b>?</b> с кратким описанием
      </motion.p>
    </div>
  );
}

// ── Страница 4 ────────────────────────────────────────────────────

function Page4() {
  const items = [
    { icon: <Layers className="w-4 h-4" />, title: "Пузыри — это темы", desc: "Чем крупнее пузырь, тем больше статей на эту тему в твоих лентах" },
    { icon: <MousePointerClick className="w-4 h-4" />, title: "Нажми на любой пузырь", desc: "Откроется список всех статей из этого кластера" },
    { icon: <RefreshCw className="w-4 h-4" />, title: "Карта обновляется", desc: "Нажми «Обновить» — и она перестроится с учётом новых статей" },
  ];

  return (
    <div className="space-y-4">
      <motion.p
        className="text-gray-600 leading-relaxed"
        style={{ fontSize: "15px" }}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        Atlas сам разберётся, о чём статьи в твоих подписках — и нарисует карту тем. Никаких настроек, просто открой раздел <b>«Карта»</b>.
      </motion.p>
      <div className="space-y-3">
        {items.map(({ icon, title, desc }, i) => (
          <motion.div
            key={title}
            className="flex gap-3 items-start"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.15 + i * 0.12, ease: "easeOut" }}
          >
            <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-blue-50 text-blue-500 flex items-center justify-center">
              {icon}
            </span>
            <div>
              <p className="text-sm font-medium text-gray-800">{title}</p>
              <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
            </div>
          </motion.div>
        ))}
      </div>
      <motion.p
        className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.55, ease: "easeOut" }}
      >
        Хочешь посмотреть только свежее? Задай период ползунком в шапке карты
      </motion.p>
    </div>
  );
}

// ── Страница 5 ────────────────────────────────────────────────────

function Page5({ onOpenProfile }: { onOpenProfile: () => void }) {
  const steps = [
    { step: "1", text: "Перейдите на", link: "developers.sber.ru", href: "https://developers.sber.ru/portal/products/gigachat-api" },
    { step: "2", text: "Войдите по номеру телефона или зарегистрируйтесь" },
    { step: "3", text: "Создайте проект GigaChat и найдите кнопку «Настроить API»" },
    { step: "4", text: "Получите Authorization Key и скопируйте его" },
  ];

  return (
    <div className="space-y-4">
      <motion.p
        className="text-gray-600 leading-relaxed"
        style={{ fontSize: "15px" }}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        Для работы QA, Дайджеста и анализа тем Atlas использует{" "}
        <b>GigaChat API</b> от Сбера. Без ключа ИИ-функции недоступны.
      </motion.p>
      <div className="space-y-2">
        <motion.p
          className="text-sm font-medium text-gray-700"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.1, ease: "easeOut" }}
        >
          Как получить ключ:
        </motion.p>
        {steps.map(({ step, text, link, href }, i) => (
          <motion.div
            key={step}
            className="flex gap-3 items-start"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.2 + i * 0.12, ease: "easeOut" }}
          >
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center font-semibold">
              {step}
            </span>
            <p className="text-sm text-gray-600 mt-0.5">
              {text}{" "}
              {link && href && (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline inline-flex items-center gap-0.5"
                >
                  {link}
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </p>
          </motion.div>
        ))}
      </div>
      <motion.p
        className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.6, ease: "easeOut" }}
      >
        После получения ключа вставьте его в профиле — кнопка ниже
        откроет нужный раздел.
      </motion.p>
      <motion.button
        onClick={onOpenProfile}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl transition-colors"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.75, ease: "easeOut" }}
      >
        Открыть профиль и добавить ключ →
      </motion.button>
    </div>
  );
}

// ── Главный компонент ─────────────────────────────────────────────

export function HandbookModal({ closable = false, onClose, onOpenProfile }: HandbookModalProps) {
  const [current, setCurrent] = useState(0);
  const [visited, setVisited] = useState<Set<number>>(new Set([0]));

  const total = PAGE_TITLES.length;

  const goTo = (index: number) => {
    if (index < current || index === current + 1) {
      setCurrent(index);
      setVisited((prev) => new Set([...prev, index]));
    }
  };

  // Навигация стрелками
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" && current < total - 1) goTo(current + 1);
      if (e.key === "ArrowLeft" && current > 0) goTo(current - 1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [current]);

  const handleOpenProfile = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    onOpenProfile();
    onClose();
  };

  const renderContent = () => {
    switch (current) {
      case 0: return <Page1 />;
      case 1: return <Page2 />;
      case 2: return <Page3 />;
      case 3: return <Page4 />;
      case 4: return <Page5 onOpenProfile={handleOpenProfile} />;
      default: return null;
    }
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center">
      {/* Затемнение */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Модал */}
      <div className="relative z-10 w-full max-w-lg mx-4 bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden">

        {/* Шапка */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <img src={atlasLogo} alt="Atlas" className="w-7 h-7 object-contain" />
            <span
              className="font-bold text-gray-900 tracking-wide uppercase text-sm"
              style={{ fontFamily: "'Inter', system-ui, sans-serif", letterSpacing: "0.15em" }}
            >
              Atlas
            </span>
            <span className="text-gray-300 text-sm">·</span>
            <span className="text-sm text-gray-500">Справочник</span>
          </div>
          {closable && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Контент — key={current} перемонтирует при смене страницы → анимации */}
        <div key={current} className="px-6 py-5 min-h-[300px]">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {PAGE_TITLES[current]}
          </h2>
          {renderContent()}
        </div>

        {/* Навигация — кружки */}
        <div className="px-6 pb-4 pt-0 flex flex-col items-center gap-2">
          <p className="text-xs text-gray-300 flex items-center gap-1">
            <span className="inline-flex items-center gap-0.5">
              <kbd className="px-1.5 py-0.5 bg-gray-100 text-gray-400 rounded text-[10px] font-mono border border-gray-200">←</kbd>
              <kbd className="px-1.5 py-0.5 bg-gray-100 text-gray-400 rounded text-[10px] font-mono border border-gray-200">→</kbd>
            </span>
            для навигации
          </p>
          <div className="flex items-center gap-3">
          {Array.from({ length: total }).map((_, i) => {
            const isCompleted = visited.has(i) && i < current;
            const isCurrent = i === current;
            const isNext = i === current + 1;
            const isAccessible = isCompleted || isCurrent || isNext;

            return (
              <button
                key={i}
                onClick={() => goTo(i)}
                disabled={!isAccessible}
                title={`Страница ${i + 1}`}
                className={`
                  w-3 h-3 rounded-full transition-all duration-200
                  ${isCompleted
                    ? "bg-green-500 hover:bg-green-600 cursor-pointer"
                    : isCurrent
                    ? "bg-blue-600 scale-125 cursor-default"
                    : isNext
                    ? "bg-gray-200 hover:bg-gray-300 cursor-pointer"
                    : "bg-gray-200 cursor-not-allowed opacity-50"
                  }
                `}
              />
            );
          })}
          </div>
        </div>

      </div>
    </div>
  );
}

// ── Хелпер для авто-показа ────────────────────────────────────────

export function shouldShowHandbook(): boolean {
  return !localStorage.getItem(STORAGE_KEY);
}
