(function () {
  "use strict";

  const API_BASE = "";

  let lastRouterSelection = null;
  let currentCollectionId = null;

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s == null ? "" : String(s);
    return div.innerHTML;
  }

  function showResult(el, content, type) {
    if (!el) return;
    el.textContent = "";
    el.hidden = false;
    el.className = "result-box " + (type || "info");
    if (typeof content === "string") {
      el.textContent = content;
    } else {
      el.appendChild(content);
    }
  }

  function showLoading(el, text) {
    const span = document.createElement("span");
    span.className = "loading";
    span.innerHTML = '<span class="spinner"></span>' + (text || "Загрузка…");
    showResult(el, span, "loading");
  }

  function showError(el, message) {
    showResult(el, message || "Произошла ошибка.", "error");
  }

  async function api(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(API_BASE + path, opts);
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_) {
      throw new Error(res.status === 502 ? "Сервер не ответил. Проверьте, что бэкенд запущен." : text || "Ошибка " + res.status);
    }
    if (!res.ok) {
      throw new Error(data?.detail || data?.message || "Ошибка " + res.status);
    }
    return data;
  }

  // ——— Роутинг ———
  const pageHome = document.getElementById("page-home");
  const pageCollection = document.getElementById("page-collection");
  const headerSubtitlePage1 = document.querySelector(".header__subtitle--page1");
  const headerSubtitlePage2 = document.querySelector(".header__subtitle--page2");

  function showPage(page) {
    if (page === "home") {
      pageHome.hidden = false;
      pageCollection.hidden = true;
      if (headerSubtitlePage1) headerSubtitlePage1.hidden = false;
      if (headerSubtitlePage2) headerSubtitlePage2.hidden = true;
    } else {
      pageHome.hidden = true;
      pageCollection.hidden = false;
      if (headerSubtitlePage1) headerSubtitlePage1.hidden = true;
      if (headerSubtitlePage2) headerSubtitlePage2.hidden = false;
    }
  }

  function parseRoute() {
    const hash = (window.location.hash || "#/").replace(/^#/, "") || "/";
    const parts = hash.split("/").filter(Boolean);
    if (parts[0] === "collection" && parts[1]) {
      const id = parseInt(parts[1], 10);
      if (!isNaN(id)) return { page: "collection", collectionId: id };
    }
    return { page: "home" };
  }

  function route() {
    const r = parseRoute();
    if (r.page === "collection") {
      currentCollectionId = r.collectionId;
      showPage("collection");
      loadCollectionPage(r.collectionId);
    } else {
      currentCollectionId = null;
      showPage("home");
      loadCollections();
    }
  }

  window.addEventListener("hashchange", route);
  window.addEventListener("load", route);

  // ——— Страница 1: Роутер + Пайплайн ———
  const routerQuery = document.getElementById("router-query");
  const routerSubmit = document.getElementById("router-submit");
  const routerResult = document.getElementById("router-result");
  const pipelineName = document.getElementById("pipeline-collection-name");
  const pipelineRun = document.getElementById("pipeline-run");
  const pipelineResult = document.getElementById("pipeline-result");

  routerSubmit.addEventListener("click", async function () {
    const query = (routerQuery.value || "").trim();
    if (!query) {
      showResult(routerResult, "Введите запрос.", "info");
      routerResult.hidden = false;
      return;
    }
    routerSubmit.disabled = true;
    showLoading(routerResult, "Подбор темы…");
    try {
      const data = await api("POST", "/api/router", { query });
      lastRouterSelection = data.selection || null;
      let msg = "Статус: " + data.status;
      if (data.selection) {
        msg += "\nD: " + (data.selection.discipline || "—") + ", GA: " + (data.selection.ga || "—") + ", A: " + (data.selection.activity || "—");
        if (data.reasoning) msg += "\n\n" + data.reasoning;
      }
      if (data.clarification_question) msg += "\n\nУточнение: " + data.clarification_question;
      showResult(routerResult, msg, data.status === "matched" ? "success" : "info");
    } catch (e) {
      showError(routerResult, e.message);
    } finally {
      routerSubmit.disabled = false;
    }
  });

  pipelineRun.addEventListener("click", async function () {
    pipelineRun.disabled = true;
    showLoading(pipelineResult, "Идёт сбор и обработка статей. Это может занять несколько минут…");
    try {
      const body = {
        taxonomy_selection: lastRouterSelection,
        collection_name: (pipelineName.value || "").trim() || null,
      };
      const data = await api("POST", "/api/pipeline/run", body);
      showResult(pipelineResult, data.message || "Пайплайн завершён. Обработано статей: " + (data.articles_count || 0) + ". Обновите список коллекций.", "success");
      loadCollections();
    } catch (e) {
      showError(pipelineResult, e.message);
    } finally {
      pipelineRun.disabled = false;
    }
  });

  // ——— Список коллекций (страница 1) ———
  const collectionsList = document.getElementById("collections-list");
  const collectionsRefresh = document.getElementById("collections-refresh");

  async function loadCollections() {
    if (!collectionsList) return;
    collectionsRefresh.disabled = true;
    collectionsList.innerHTML = "";
    try {
      const data = await api("GET", "/api/collections");
      if (!data || data.length === 0) {
        collectionsList.innerHTML = '<p class="hint">Нет коллекций. Запустите пайплайн выше.</p>';
        return;
      }
      data.forEach(function (c) {
        const div = document.createElement("div");
        div.className = "collection-item";
        const meta = [c.discipline, c.ga, c.activity].filter(Boolean).join(" / ") || "—";
        const openBtn = document.createElement("button");
        openBtn.type = "button";
        openBtn.className = "btn btn--primary collection-item__open";
        openBtn.textContent = "Открыть";
        openBtn.addEventListener("click", function () {
          window.location.hash = "#/collection/" + c.id;
        });
        div.innerHTML =
          '<span class="collection-item__name">' + escapeHtml(c.name) + "</span>" +
          '<span class="collection-item__meta">' + escapeHtml(meta) + "</span>" +
          '<span class="collection-item__id">id: ' + c.id + "</span>";
        div.appendChild(openBtn);
        collectionsList.appendChild(div);
      });
    } catch (e) {
      collectionsList.innerHTML = '<p class="result-box error">' + escapeHtml(e.message) + "</p>";
    } finally {
      collectionsRefresh.disabled = false;
    }
  }

  collectionsRefresh.addEventListener("click", loadCollections);

  // ——— Страница 2: Коллекция (статьи + Q&A) ———
  const collectionTitleEl = document.getElementById("collection-title");
  const collectionMetaEl = document.getElementById("collection-meta");
  const articlesList = document.getElementById("articles-list");
  const digestBuildBtn = document.getElementById("digest-build");
  const digestResult = document.getElementById("digest-result");
  const qaQuestion = document.getElementById("qa-question");
  const qaSubmit = document.getElementById("qa-submit");
  const qaResult = document.getElementById("qa-result");

  var sectionTitles = {
    key_trends: "Ключевые тренды",
    methods: "Методы и подходы",
    tools: "Инструменты",
    case_studies: "Кейсы",
  };

  async function loadCollectionPage(collectionId) {
    if (!collectionTitleEl || !collectionMetaEl || !articlesList) return;
    collectionTitleEl.textContent = "Загрузка…";
    collectionMetaEl.textContent = "";
    articlesList.innerHTML = '<p class="hint">Загрузка статей…</p>';
    if (digestResult) {
      digestResult.hidden = true;
      digestResult.innerHTML = "";
    }

    try {
      const [coll, articles] = await Promise.all([
        api("GET", "/api/collections/" + collectionId),
        api("GET", "/api/collections/" + collectionId + "/articles"),
      ]);
      collectionTitleEl.textContent = coll.name || "Коллекция";
      const meta = [coll.discipline, coll.ga, coll.activity].filter(Boolean).join(" / ") || "—";
      collectionMetaEl.textContent = meta + " (id: " + coll.id + ")";

      articlesList.innerHTML = "";
      if (!articles || articles.length === 0) {
        articlesList.innerHTML = '<p class="hint">В коллекции пока нет статей.</p>';
        return;
      }
      articles.forEach(function (a) {
        const card = document.createElement("div");
        card.className = "article-card";
        const title = (a.title || a.link || "Без названия").trim();
        const summary = (a.summary || "").trim();
        card.innerHTML =
          '<div class="article-card__title"><a href="' + escapeHtml(a.link) + '" target="_blank" rel="noopener">' + escapeHtml(title) + "</a></div>" +
          (summary ? '<div class="article-card__summary">' + escapeHtml(summary) + "</div>" : "") +
          '<div class="article-card__link"><a href="' + escapeHtml(a.link) + '" target="_blank" rel="noopener">' + escapeHtml(a.link) + "</a></div>";
        articlesList.appendChild(card);
      });
    } catch (e) {
      collectionTitleEl.textContent = "Ошибка";
      collectionMetaEl.textContent = "";
      articlesList.innerHTML = '<p class="result-box error">' + escapeHtml(e.message) + "</p>";
    }
  }

  if (digestBuildBtn && digestResult) {
    digestBuildBtn.addEventListener("click", async function () {
      var cid = currentCollectionId;
      if (!cid) return;
      digestBuildBtn.disabled = true;
      digestResult.hidden = false;
      digestResult.innerHTML = '<p class="result-box loading"><span class="spinner"></span>Формирование дайджеста…</p>';
      try {
        var data = await api("GET", "/api/digest/" + cid);
        digestResult.innerHTML = "";
        var wrap = document.createElement("div");
        wrap.className = "digest-box";
        var metaP = document.createElement("p");
        metaP.className = "hint";
        metaP.textContent = (data.collection_meta && data.collection_meta.name ? data.collection_meta.name + " · " : "") + (data.generated_at || "");
        wrap.appendChild(metaP);
        var sections = data.sections || {};
        Object.keys(sectionTitles).forEach(function (key) {
          var items = sections[key];
          if (!items || items.length === 0) return;
          var section = document.createElement("div");
          section.className = "digest-section";
          section.innerHTML = "<h3>" + escapeHtml(sectionTitles[key]) + "</h3><ul></ul>";
          var ul = section.querySelector("ul");
          items.forEach(function (item) {
            var label = item.label || item.description || "";
            var li = document.createElement("li");
            li.innerHTML = escapeHtml(label);
            var articles = item.articles || [];
            if (articles.length > 0) {
              var sub = document.createElement("ul");
              articles.forEach(function (a) {
                var subLi = document.createElement("li");
                var link = document.createElement("a");
                link.href = a.link;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = a.title || a.link;
                subLi.appendChild(link);
                sub.appendChild(subLi);
              });
              li.appendChild(sub);
            }
            ul.appendChild(li);
          });
          wrap.appendChild(section);
        });
        digestResult.appendChild(wrap);
      } catch (e) {
        digestResult.innerHTML = '<p class="result-box error">' + escapeHtml(e.message) + "</p>";
      } finally {
        digestBuildBtn.disabled = false;
      }
    });
  }

  qaSubmit.addEventListener("click", async function () {
    const cid = currentCollectionId;
    const question = (qaQuestion.value || "").trim();
    if (!cid || !question) {
      showResult(qaResult, "Введите вопрос.", "info");
      qaResult.hidden = false;
      return;
    }
    qaSubmit.disabled = true;
    showLoading(qaResult, "Формирование ответа по статьям этой коллекции…");
    try {
      const data = await api("POST", "/api/qa", { question, collection_id: cid });
      if (data.status === "error") {
        showError(qaResult, data.error || "Ошибка QA");
        return;
      }
      const wrap = document.createElement("div");
      const answerDiv = document.createElement("div");
      answerDiv.className = "qa-answer";
      answerDiv.textContent = data.answer || "Ответ не получен.";
      wrap.appendChild(answerDiv);
      if (data.sources && data.sources.length > 0) {
        const srcDiv = document.createElement("div");
        srcDiv.className = "qa-sources";
        srcDiv.innerHTML = "<h4>Источники (статьи коллекции)</h4><ul></ul>";
        const ul = srcDiv.querySelector("ul");
        data.sources.forEach(function (s) {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = s.link;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = s.title || s.link;
          li.appendChild(a);
          ul.appendChild(li);
        });
        wrap.appendChild(srcDiv);
      }
      showResult(qaResult, wrap, "success");
    } catch (e) {
      showError(qaResult, e.message);
    } finally {
      qaSubmit.disabled = false;
    }
  });
})();
