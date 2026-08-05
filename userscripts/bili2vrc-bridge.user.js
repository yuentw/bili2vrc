// ==UserScript==
// @name         bili2vrc Bridge
// @namespace    https://github.com/yuentw/bili2vrc
// @version      1.0.7
// @description  Bilibili 封面懸浮「下載解析」→ 開啟 bili2vrc 並自動填入網址、獲取格式
// @author       bili2vrc
// @match        https://www.bilibili.com/*
// @match        https://search.bilibili.com/*
// @match        https://space.bilibili.com/*
// @match        https://t.bilibili.com/*
// @grant        GM_addStyle
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const STORAGE_KEY = 'bili2vrc_base';
  const DEFAULT_BASE = 'http://localhost:5000';
  const BTN_CLASS = 'b2v-cover-btn';
  const FIXED_ID = 'b2v-fixed-btn';
  const HOST_ATTR = 'data-b2v-host';

  // Never touch Bilibili top nav mount point / channel header
  const HEADER_EXCLUDE = [
    '#biliMainHeader',
    '#bili-header-container',
    '#internationalHeader',
    '.bili-header',
    '.bili-header-m',
    '.fixed-header',
    '.mini-header',
    '.international-header',
    '.header-channel',
    '.header-channel-fixed',
    '.biliMainHeaderWrapper',
    'header',
    'nav',
  ].join(', ');

  // Observe only content regions — never #app/#biliMainHeader/body (breaks header micro-frontend)
  const OBSERVE_ROOT_SELECTORS = [
    '#mirror-vdcon',
    '.recommend-list-v1',
    '.recommend-list-container',
    '#reco_list',
    '.right-container',
    '.fav-list-main',
    '.fav-video-list',
    '.section-cards',
    '.video-list',
    '.feed-card',
    '.bili-feed4-layout',
    '.search-content',
    '.bili-video-card__wrap',
    '.video-page-card-small',
  ];

  const COVER_SELECTORS = [
    '.video-card .pic-box',
    '.bili-video-card .bili-video-card__image',
    '.bili-video-card__image--wrap',
    '.bili-video-card__cover',
    '.bili-cover-card',
    '.bili-cover-card__thumbnail',
    '.small-item .cover',
    '.card-pic',
    '.list-item .cover',
    '.bili-dyn-card-video__cover',
    '.video-page-card-small .pic-box',
    '.video-page-card-small .card-box .pic-box',
    '.video-page-operator-card-small .pic-box',
    '.next-play .pic-box',
    '.recommend-list-v1 .pic-box',
    '.recommend-list-container .pic-box',
    '#reco_list .pic-box',
    '.right-container .pic-box',
    '.history-card .bili-video-card__cover',
    '.history-card .bili-cover-card',
    '.history-card .bili-cover-card__thumbnail',
    '.section-cards .bili-cover-card',
    '.fav-list-main .bili-video-card__image',
    '.fav-list-main .bili-video-card__image--wrap',
    '.fav-list-main .bili-cover-card',
    '.items__item .bili-video-card__image',
    '.items__item .bili-video-card__image--wrap',
    '.items__item .bili-cover-card',
    '.fav-video-list .cover',
    '.fav-video-list li > a.cover',
    'ul.fav-video-list .cover',
  ];

  const FAV_ITEM_SELECTORS = [
    '.fav-list-main .items__item',
    '.fav-video-list > li',
    'ul.fav-video-list li',
  ];

  const FAV_COVER_INNER = [
    '.bili-video-card__image',
    '.bili-video-card__image--wrap',
    '.bili-video-card__cover',
    '.bili-cover-card',
    'a.cover',
    '.cover',
    '.pic-box',
  ].join(', ');

  const HISTORY_ITEM_SELECTORS = [
    '.history-card',
    '.section-cards .history-card',
  ];

  const HISTORY_COVER_INNER = [
    '.bili-video-card__cover',
    '.bili-cover-card',
    '.bili-cover-card__thumbnail',
  ].join(', ');

  const RELATED_ITEM_SELECTORS = [
    '.video-page-card-small',
    '.video-page-operator-card-small',
    '.next-play',
    '#reco_list .video-page-card-small',
    '.recommend-list-v1 .video-page-card-small',
    '.recommend-list-container .video-page-card-small',
    '.right-container .video-page-card-small',
  ];

  const RELATED_COVER_INNER = [
    '.pic-box',
    '.card-box .pic-box',
    'a.pic-box',
    '.cover',
  ].join(', ');

  const TITLE_OR_INFO_SELECTOR = [
    '.bili-video-card__info',
    '.bili-video-card__info--right',
    '.bili-video-card__info--tit',
    '.video-card__info',
    '.up-info',
  ].join(', ');

  function inHeader(element) {
    return Boolean(element?.closest?.(HEADER_EXCLUDE));
  }

  function getBaseUrl() {
    const saved = (typeof GM_getValue === 'function' ? GM_getValue(STORAGE_KEY, '') : '') || '';
    const trimmed = String(saved).trim().replace(/\/+$/, '');
    return trimmed || DEFAULT_BASE;
  }

  function setBaseUrl(value) {
    const cleaned = String(value || '').trim().replace(/\/+$/, '');
    if (typeof GM_setValue === 'function') {
      GM_setValue(STORAGE_KEY, cleaned || DEFAULT_BASE);
    }
  }

  function extractBvid(text) {
    const match = String(text || '').match(/BV[a-zA-Z0-9]+/);
    return match ? match[0] : null;
  }

  function videoUrlFromBvid(bvid) {
    return `https://www.bilibili.com/video/${bvid}`;
  }

  function openInBili2vrc(videoUrl) {
    const base = getBaseUrl();
    const target = `${base}/?url=${encodeURIComponent(videoUrl)}`;
    window.open(target, '_blank', 'noopener,noreferrer');
  }

  function findBvidNear(element) {
    if (!(element instanceof Element)) return null;
    if (inHeader(element)) return null;

    const link =
      (element.matches?.('a[href]') && element) ||
      element.querySelector?.('a[href*="/video/"], a[href*="bvid="]') ||
      element.closest?.('a[href*="/video/"], a[href*="bvid="]');

    const fromHref = extractBvid(link?.href || link?.getAttribute?.('href') || '');
    if (fromHref) return fromHref;

    const fromHost = extractBvid(
      element.getAttribute('href') ||
      element.closest?.('[href]')?.getAttribute('href') ||
      '',
    );
    if (fromHost) return fromHost;

    const card = element.closest?.(
      [
        '.bili-video-card',
        '.video-card',
        '.video-page-card-small',
        '.video-page-operator-card-small',
        '.next-play',
        '.history-card',
        '.small-item',
        '.bili-dyn-card-video',
        '[data-bvid]',
        '.items__item',
        '.fav-video-list li',
      ].join(', '),
    );
    if (card) {
      if (inHeader(card)) return null;
      const dataBvid =
        card.getAttribute('data-bvid') ||
        card.querySelector?.('[data-bvid]')?.getAttribute('data-bvid');
      if (dataBvid && extractBvid(dataBvid)) return extractBvid(dataBvid);
      const nested = card.querySelector(
        'a[href*="/video/"], a[href*="bvid="], a[href*="/list/"]',
      );
      const nestedBvid = extractBvid(nested?.href || nested?.getAttribute('href') || '');
      if (nestedBvid) return nestedBvid;
      const titleLink = card.querySelector(
        '.bili-video-card__title a[href], .title a[href], a.title[href], .info a[href]',
      );
      const titleBvid = extractBvid(titleLink?.href || titleLink?.getAttribute('href') || '');
      if (titleBvid) return titleBvid;
      const fromCardHtml = extractBvid(card.innerHTML || '');
      if (fromCardHtml) return fromCardHtml;
    }
    return null;
  }

  function isCoverHost(element) {
    if (!(element instanceof Element)) return false;
    if (inHeader(element)) return false;
    if (element.closest(TITLE_OR_INFO_SELECTOR) && !element.matches(COVER_SELECTORS.join(', '))) {
      return false;
    }
    return element.matches(COVER_SELECTORS.join(', '));
  }

  function ensureHostPosition(host) {
    const position = window.getComputedStyle(host).position;
    if (position === 'static') {
      host.style.position = 'relative';
    }
    host.setAttribute(HOST_ATTR, '1');
  }

  function attachCoverButton(host) {
    if (!(host instanceof Element)) return;
    if (inHeader(host)) return;
    if (!isCoverHost(host)) return;
    if (host.querySelector(`:scope > .${BTN_CLASS}`)) return;
    if (host.parentElement?.closest(`[${HOST_ATTR}]`)) return;

    const bvid = findBvidNear(host);
    if (!bvid) return;

    ensureHostPosition(host);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = BTN_CLASS;
    btn.textContent = '下載解析';
    btn.title = '在 bili2vrc 開啟並獲取格式';
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openInBili2vrc(videoUrlFromBvid(bvid));
    });
    host.appendChild(btn);
  }

  function removeStrayButtons() {
    document.querySelectorAll(`.${BTN_CLASS}`).forEach((btn) => {
      const host = btn.parentElement;
      if (!host || inHeader(host) || !isCoverHost(host)) {
        btn.remove();
        if (host?.hasAttribute?.(HOST_ATTR) && !host.querySelector(`.${BTN_CLASS}`)) {
          host.removeAttribute(HOST_ATTR);
          if (host.style.position === 'relative') host.style.position = '';
        }
      }
    });
  }

  function scanFavlistCovers(root = document) {
    FAV_ITEM_SELECTORS.forEach((itemSel) => {
      root.querySelectorAll?.(itemSel)?.forEach((item) => {
        if (inHeader(item)) return;
        const cover = item.querySelector(FAV_COVER_INNER);
        if (cover) attachCoverButton(cover);
      });
    });
  }

  function scanHistoryCovers(root = document) {
    HISTORY_ITEM_SELECTORS.forEach((itemSel) => {
      root.querySelectorAll?.(itemSel)?.forEach((item) => {
        if (inHeader(item)) return;
        const cover =
          item.querySelector('.bili-cover-card') ||
          item.querySelector(HISTORY_COVER_INNER);
        if (cover) attachCoverButton(cover);
      });
    });
  }

  function scanRelatedCovers(root = document) {
    RELATED_ITEM_SELECTORS.forEach((itemSel) => {
      root.querySelectorAll?.(itemSel)?.forEach((item) => {
        if (inHeader(item)) return;
        const cover = item.querySelector(RELATED_COVER_INNER);
        if (cover) attachCoverButton(cover);
      });
    });
  }

  function scanCovers(root = document) {
    removeStrayButtons();
    COVER_SELECTORS.forEach((selector) => {
      root.querySelectorAll?.(selector)?.forEach((el) => {
        if (!inHeader(el)) attachCoverButton(el);
      });
    });
    scanFavlistCovers(root);
    scanHistoryCovers(root);
    scanRelatedCovers(root);
  }

  function ensureWatchPageButton() {
    const pathBvid = extractBvid(location.pathname + location.search);
    if (!pathBvid || !location.pathname.includes('/video/')) {
      document.getElementById(FIXED_ID)?.remove();
      return;
    }
    if (document.getElementById(FIXED_ID)) return;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = FIXED_ID;
    btn.textContent = '下載解析';
    btn.title = '在 bili2vrc 開啟並獲取格式';
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openInBili2vrc(videoUrlFromBvid(pathBvid));
    });
    (document.body || document.documentElement).appendChild(btn);
  }

  function isOurNode(node) {
    return (
      node instanceof Element &&
      (node.id === FIXED_ID ||
        node.classList?.contains(BTN_CLASS) ||
        node.hasAttribute?.(HOST_ATTR))
    );
  }

  function mutationsAreOurs(mutations) {
    if (!mutations?.length) return false;
    return mutations.every((mutation) => {
      const nodes = [...mutation.addedNodes, ...mutation.removedNodes];
      if (!nodes.length) {
        return mutation.type === 'attributes' && isOurNode(mutation.target);
      }
      return nodes.every(
        (node) =>
          isOurNode(node) ||
          (node.parentElement && isOurNode(node.parentElement)),
      );
    });
  }

  function debounce(fn, waitMs) {
    let timer = 0;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), waitMs);
    };
  }

  function injectStyles() {
    GM_addStyle(`
      .${BTN_CLASS} {
        position: absolute !important;
        top: 8px !important;
        right: 8px !important;
        left: auto !important;
        bottom: auto !important;
        z-index: 30 !important;
        padding: 10px 16px !important;
        min-width: 88px !important;
        border: none !important;
        border-radius: 8px !important;
        background: rgba(236, 72, 153, 0.95) !important;
        color: #fff !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        line-height: 1.2 !important;
        letter-spacing: 0.02em !important;
        cursor: pointer !important;
        opacity: 0 !important;
        pointer-events: auto !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4) !important;
        transition: opacity 0.15s ease, transform 0.15s ease !important;
      }
      [${HOST_ATTR}]:hover > .${BTN_CLASS},
      a:hover > .${BTN_CLASS},
      .video-card:hover .${BTN_CLASS},
      .bili-video-card:hover .${BTN_CLASS},
      .video-page-card-small:hover .${BTN_CLASS},
      .video-page-operator-card-small:hover .${BTN_CLASS},
      .next-play:hover .${BTN_CLASS},
      .history-card:hover .${BTN_CLASS},
      .bili-cover-card:hover .${BTN_CLASS},
      .bili-video-card__cover:hover .${BTN_CLASS},
      .items__item:hover .${BTN_CLASS},
      .fav-video-list li:hover .${BTN_CLASS},
      .fav-list-main .items__item:hover .${BTN_CLASS},
      .pic-box:hover .${BTN_CLASS} {
        opacity: 1 !important;
      }
      .${BTN_CLASS}:hover {
        opacity: 1 !important;
        transform: scale(1.05) !important;
        background: rgba(236, 72, 153, 1) !important;
        color: #fff !important;
      }
      #${FIXED_ID} {
        position: fixed !important;
        right: 20px !important;
        bottom: 96px !important;
        z-index: 99999 !important;
        padding: 12px 18px !important;
        border: none !important;
        border-radius: 8px !important;
        background: rgba(236, 72, 153, 0.95) !important;
        color: #fff !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        cursor: pointer !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35) !important;
      }
      #${FIXED_ID}:hover {
        background: rgb(236, 72, 153) !important;
      }
    `);
  }

  function registerMenu() {
    if (typeof GM_registerMenuCommand !== 'function') return;
    GM_registerMenuCommand('設定 bili2vrc 網址', () => {
      const current = getBaseUrl();
      const next = window.prompt('bili2vrc 網址（例：http://localhost:5000）', current);
      if (next == null) return;
      setBaseUrl(next);
      window.alert(`已設定為：${getBaseUrl()}`);
    });
  }

  function headerReady() {
    const mount = document.getElementById('biliMainHeader');
    if (!mount) return true; // pages without this mount
    return Boolean(mount.querySelector('.bili-header, .bili-header__bar, .mini-header'));
  }

  function waitForHeader(timeoutMs = 8000) {
    return new Promise((resolve) => {
      if (headerReady()) {
        resolve(true);
        return;
      }
      const started = Date.now();
      const timer = window.setInterval(() => {
        if (headerReady() || Date.now() - started > timeoutMs) {
          window.clearInterval(timer);
          resolve(headerReady());
        }
      }, 100);
    });
  }

  function collectObserveRoots() {
    const roots = [];
    const seen = new Set();
    OBSERVE_ROOT_SELECTORS.forEach((selector) => {
      document.querySelectorAll(selector).forEach((el) => {
        if (inHeader(el) || seen.has(el)) return;
        // Never observe the header mount itself
        if (el.id === 'biliMainHeader') return;
        seen.add(el);
        roots.push(el);
      });
    });
    return roots;
  }

  function startObservers(rescan) {
    const observers = [];
    const attach = (root) => {
      const observer = new MutationObserver((mutations) => {
        if (mutationsAreOurs(mutations)) return;
        // Ignore mutations inside header mount
        if (mutations.every((m) => inHeader(m.target))) return;
        rescan();
      });
      observer.observe(root, { childList: true, subtree: true });
      observers.push(observer);
    };

    collectObserveRoots().forEach(attach);

    // Watch for late-appearing content roots without observing whole body
    const boot = new MutationObserver(() => {
      collectObserveRoots().forEach((root) => {
        if (root.__b2vObserved) return;
        root.__b2vObserved = true;
        attach(root);
        rescan();
      });
    });
    // Only watch direct children of #app / body for new major sections
    const app = document.getElementById('app') || document.body;
    if (app) {
      boot.observe(app, { childList: true, subtree: false });
      observers.push(boot);
    }
    return observers;
  }

  async function init() {
    injectStyles();
    registerMenu();

    // Critical: wait until Bilibili header micro-frontend mounts.
    // Full-document MutationObserver previously emptied #biliMainHeader.
    await waitForHeader(8000);
    // Extra settle time after header appears
    await new Promise((resolve) => window.setTimeout(resolve, 300));

    const rescan = debounce(() => {
      scanCovers();
      ensureWatchPageButton();
    }, 400);

    scanCovers();
    ensureWatchPageButton();
    startObservers(rescan);

    window.addEventListener('scroll', () => rescan(), { passive: true });

    let lastHref = location.href;
    setInterval(() => {
      if (location.href !== lastHref) {
        lastHref = location.href;
        waitForHeader(5000).then(() => {
          window.setTimeout(() => rescan(), 300);
        });
      }
    }, 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      void init();
    }, { once: true });
  } else {
    void init();
  }
})();
