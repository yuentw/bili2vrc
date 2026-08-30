// ==UserScript==
// @name         bili2vrc Bridge
// @namespace    https://github.com/yuentw/bili2vrc
// @version      1.1.0
// @description  Bilibili / YouTube 封面懸浮「下載解析」→ 開啟 bili2vrc 並自動填入網址、獲取格式
// @author       bili2vrc
// @match        https://www.bilibili.com/*
// @match        https://search.bilibili.com/*
// @match        https://space.bilibili.com/*
// @match        https://t.bilibili.com/*
// @match        https://www.youtube.com/*
// @match        https://m.youtube.com/*
// @match        https://youtu.be/*
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
  const YT_WATCH_BTN_ID = 'b2v-yt-watch-btn';
  const YT_THANKS_STACK = 'b2v-yt-thanks-stack';
  const HOST_ATTR = 'data-b2v-host';
  // First cover scan delay — give Bilibili header micro-frontend time to mount (esp. 4K / slow loads).
  const FIRST_SCAN_DELAY_MS = 1800;
  const RESCAN_DEBOUNCE_MS = 450;

  // Never touch Bilibili top nav mount point / channel header
  const HEADER_EXCLUDE = [
    '#biliMainHeader',
    '#bili-header-container',
    '#biliHeader',
    '#internationalHeader',
    '.bili-header',
    '.bili-header-m',
    '.bili-header__bar',
    '.bili-header__channel',
    '.fixed-header',
    '.mini-header',
    '.international-header',
    '.header-channel',
    '.header-channel-fixed',
    '.header-channel-fixed-left',
    '.biliMainHeaderWrapper',
    '.bili-header-channel-panel',
    '.v-popover',
    'bili-header',
    'header',
    'nav',
  ].join(', ');

  const YT_HEADER_EXCLUDE = [
    'ytd-masthead',
    '#masthead-container',
    '#masthead',
    '#masthead-positioner',
    'ytm-mobile-topbar-renderer',
  ].join(', ');

  const YT_COVER_SELECTORS = [
    'ytd-thumbnail',
    'a#thumbnail',
    'a.ytLockupViewModelContentImage',
    'a.ytLockupViewModelHostContentImage',
    'a.yt-lockup-view-model-wiz__content-image',
    'a.yt-lockup-view-model__content-image',
    'yt-lockup-view-model a:has(yt-thumbnail-view-model)',
    'yt-thumbnail-view-model',
    'ytd-reel-item-renderer ytd-thumbnail',
    'ytm-shorts-lockup-view-model',
    '.shortsLockupViewModelHostThumbnailContainer',
    'a.media-item-thumbnail-container',
    'ytm-media-item .media-item-thumbnail',
  ];

  const YT_ITEM_SELECTORS = [
    'ytd-rich-item-renderer',
    'ytd-video-renderer',
    'ytd-grid-video-renderer',
    'ytd-compact-video-renderer',
    'ytd-reel-item-renderer',
    'ytd-rich-grid-media',
    'ytd-rich-grid-slim-media',
    'yt-lockup-view-model',
    'ytm-rich-item-renderer',
    'ytm-video-with-context-renderer',
    'ytm-compact-video-renderer',
  ];

  const YT_COVER_INNER = [
    'ytd-thumbnail',
    'a#thumbnail',
    'a.ytLockupViewModelContentImage',
    'a.ytLockupViewModelHostContentImage',
    'a.yt-lockup-view-model-wiz__content-image',
    'a.yt-lockup-view-model__content-image',
    'a:has(yt-thumbnail-view-model)',
    'yt-thumbnail-view-model',
    'ytm-shorts-lockup-view-model',
    '.shortsLockupViewModelHostThumbnailContainer',
    'a.media-item-thumbnail-container',
  ].join(', ');

  const YT_CARD_SELECTOR = [
    'ytd-rich-item-renderer',
    'ytd-video-renderer',
    'ytd-grid-video-renderer',
    'ytd-compact-video-renderer',
    'ytd-reel-item-renderer',
    'ytd-rich-grid-media',
    'ytd-rich-grid-slim-media',
    'ytd-reel-video-renderer',
    'yt-lockup-view-model',
    'ytm-rich-item-renderer',
    'ytm-video-with-context-renderer',
    'ytm-compact-video-renderer',
    'ytm-shorts-lockup-view-model',
  ].join(', ');

  const YT_LINK_SELECTOR =
    'a[href*="/watch"], a[href*="/shorts/"], a[href*="youtu.be/"], a#thumbnail[href]';

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
    '#meta.ytd-video-renderer',
    '#details.ytd-rich-grid-media',
    '#dismissible > #details',
  ].join(', ');

  function isYouTubeHost() {
    const host = location.hostname;
    return host === 'www.youtube.com' || host === 'm.youtube.com' || host === 'youtu.be';
  }

  function inHeader(element) {
    if (!(element instanceof Node)) return false;
    const el = element.nodeType === Node.ELEMENT_NODE ? element : element.parentElement;
    if (!el?.closest) return false;
    if (el.closest(HEADER_EXCLUDE)) return true;
    if (isYouTubeHost() && el.closest(YT_HEADER_EXCLUDE)) return true;
    // Header often mounts as a custom element / portal near documentElement.
    const id = (el.id || '').toLowerCase();
    const cls = typeof el.className === 'string' ? el.className.toLowerCase() : '';
    return (
      id.includes('header') ||
      cls.includes('bili-header') ||
      cls.includes('bilimainheader') ||
      cls.includes('header-channel')
    );
  }

  function nodeLooksLikeHeader(node) {
    if (!(node instanceof Element)) return false;
    if (inHeader(node)) return true;
    try {
      if (node.matches?.(HEADER_EXCLUDE)) return true;
      if (node.querySelector?.(HEADER_EXCLUDE)) return true;
    } catch {
      /* invalid selector match on exotic nodes */
    }
    return false;
  }

  function mutationsTouchHeader(mutations) {
    if (!mutations?.length) return false;
    for (const mutation of mutations) {
      if (inHeader(mutation.target)) return true;
      for (const node of mutation.addedNodes) {
        if (nodeLooksLikeHeader(node)) return true;
      }
      for (const node of mutation.removedNodes) {
        if (nodeLooksLikeHeader(node)) return true;
      }
    }
    return false;
  }

  function runWhenIdle(fn) {
    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(() => fn(), { timeout: 1200 });
      return;
    }
    window.setTimeout(fn, 0);
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

  function extractYoutubeVideoId(text) {
    const raw = String(text || '');
    const watchMatch = raw.match(/[?&]v=([a-zA-Z0-9_-]{11})(?:[^a-zA-Z0-9_-]|$)/);
    if (watchMatch) return watchMatch[1];
    const shortsMatch = raw.match(/\/shorts\/([a-zA-Z0-9_-]{11})(?:[/?#]|$)/);
    if (shortsMatch) return shortsMatch[1];
    const shortLinkMatch = raw.match(/youtu\.be\/([a-zA-Z0-9_-]{11})(?:[/?#]|$)/);
    if (shortLinkMatch) return shortLinkMatch[1];
    const embedMatch = raw.match(/\/embed\/([a-zA-Z0-9_-]{11})(?:[/?#]|$)/);
    if (embedMatch) return embedMatch[1];
    const liveMatch = raw.match(/\/live\/([a-zA-Z0-9_-]{11})(?:[/?#]|$)/);
    if (liveMatch) return liveMatch[1];
    return null;
  }

  function youtubeCanonicalUrl(hrefOrPath) {
    const source = String(hrefOrPath || '');
    const videoId = extractYoutubeVideoId(source);
    if (!videoId) return null;
    if (/\/shorts\//.test(source)) {
      return `https://www.youtube.com/shorts/${videoId}`;
    }
    return `https://www.youtube.com/watch?v=${videoId}`;
  }

  function findYoutubeUrlNear(element) {
    if (!(element instanceof Element)) return null;
    if (inHeader(element)) return null;

    const link =
      (element.matches?.('a[href]') && element) ||
      element.querySelector?.(YT_LINK_SELECTOR) ||
      element.closest?.(YT_LINK_SELECTOR);

    const fromHref = youtubeCanonicalUrl(link?.href || link?.getAttribute?.('href') || '');
    if (fromHref) return fromHref;

    const card = element.closest?.(YT_CARD_SELECTOR);
    if (card) {
      if (inHeader(card)) return null;
      const nested = card.querySelector(YT_LINK_SELECTOR);
      const nestedUrl = youtubeCanonicalUrl(nested?.href || nested?.getAttribute('href') || '');
      if (nestedUrl) return nestedUrl;
    }
    return null;
  }

  function findVideoUrlNear(element) {
    if (isYouTubeHost()) return findYoutubeUrlNear(element);
    const bvid = findBvidNear(element);
    return bvid ? videoUrlFromBvid(bvid) : null;
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

  function coverSelectorList() {
    return isYouTubeHost() ? YT_COVER_SELECTORS : COVER_SELECTORS;
  }

  function isCoverHost(element) {
    if (!(element instanceof Element)) return false;
    if (inHeader(element)) return false;
    if (isYouTubeHost()) {
      const youtubeSelectors = [...YT_COVER_SELECTORS, ...YT_ITEM_SELECTORS].join(', ');
      try {
        return element.matches(youtubeSelectors);
      } catch {
        return YT_ITEM_SELECTORS.some((selector) => element.matches(selector));
      }
    }
    const coverSelectors = COVER_SELECTORS.join(', ');
    if (element.closest(TITLE_OR_INFO_SELECTOR) && !element.matches(coverSelectors)) {
      return false;
    }
    return element.matches(coverSelectors);
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
    if (host.querySelector(`.${BTN_CLASS}`)) return;
    if (host.parentElement?.closest(`[${HOST_ATTR}]`)) return;

    if (!findVideoUrlNear(host)) return;

    ensureHostPosition(host);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = BTN_CLASS;
    btn.textContent = '下載解析';
    btn.title = '在 bili2vrc 開啟並獲取格式';
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const liveUrl = findVideoUrlNear(host);
      if (!liveUrl) return;
      openInBili2vrc(liveUrl);
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

  function findYoutubeCoverHost(item) {
    let inner = null;
    try {
      inner = item.querySelector(YT_COVER_INNER);
    } catch {
      inner = item.querySelector(
        'ytd-thumbnail, a#thumbnail, a.ytLockupViewModelContentImage, yt-thumbnail-view-model',
      );
    }
    if (inner) {
      const wrapLink = inner.closest('a[href*="/watch"], a[href*="/shorts/"]');
      if (wrapLink && item.contains(wrapLink)) return wrapLink;
      return inner;
    }
    const anchors = item.querySelectorAll('a[href*="/watch"], a[href*="/shorts/"]');
    for (const anchor of anchors) {
      if (inHeader(anchor)) continue;
      if (anchor.querySelector('img, yt-image, yt-thumbnail-view-model, ytd-moving-thumbnail-renderer')) {
        return anchor;
      }
    }
    if (anchors.length) return anchors[0];
    if (item.matches('yt-lockup-view-model') && item.parentElement) return item.parentElement;
    if (window.getComputedStyle(item).display === 'contents' && item.firstElementChild) {
      return item.firstElementChild;
    }
    return item;
  }

  function scanYoutubeCovers(root = document) {
    YT_ITEM_SELECTORS.forEach((itemSel) => {
      root.querySelectorAll?.(itemSel)?.forEach((item) => {
        if (inHeader(item)) return;
        if (item.querySelector(`.${BTN_CLASS}`)) return;
        const cover = findYoutubeCoverHost(item);
        if (cover) attachCoverButton(cover);
      });
    });
  }

  function scanCovers(root = document) {
    removeStrayButtons();
    coverSelectorList().forEach((selector) => {
      let nodes;
      try {
        nodes = root.querySelectorAll?.(selector);
      } catch {
        return;
      }
      nodes?.forEach((el) => {
        if (!inHeader(el)) attachCoverButton(el);
      });
    });
    if (isYouTubeHost()) {
      scanYoutubeCovers(root);
      return;
    }
    scanFavlistCovers(root);
    scanHistoryCovers(root);
    scanRelatedCovers(root);
  }

  function isYoutubeFullscreen() {
    return Boolean(
      document.fullscreenElement ||
      document.webkitFullscreenElement ||
      document.querySelector('ytd-watch-flexy[fullscreen]'),
    );
  }

  function findYoutubeLikeHost() {
    const roots = [
      document.querySelector('ytd-watch-metadata #actions'),
      document.querySelector('#below #actions'),
      document.querySelector('#actions'),
    ].filter(Boolean);
    const hostSelectors = [
      'segmented-like-dislike-button-view-model',
      'ytd-segmented-like-dislike-button-renderer',
      'like-button-view-model',
    ];
    for (const root of roots) {
      for (const selector of hostSelectors) {
        const el = root.querySelector(selector);
        if (el) return el;
      }
      const likeBtn = [...root.querySelectorAll('button[aria-label]')].find((el) => {
        const label = el.getAttribute('aria-label') || '';
        return /讚|喜歡|like this|\blike\b/i.test(label) && !/dislike|倒讚|不喜歡/i.test(label);
      });
      if (likeBtn) {
        return (
          likeBtn.closest(
            'segmented-like-dislike-button-view-model, ytd-segmented-like-dislike-button-renderer, like-button-view-model, yt-button-view-model',
          ) || likeBtn
        );
      }
    }
    return null;
  }

  function findYoutubeActionsRow() {
    return (
      document.querySelector('#top-level-buttons-computed') ||
      document.querySelector('#flexible-item-buttons') ||
      document.querySelector('ytd-watch-metadata #actions') ||
      document.querySelector('#below #actions')
    );
  }

  function unwrapYoutubeThanksStack() {
    document.querySelectorAll(`.${YT_THANKS_STACK}`).forEach((stack) => {
      const parent = stack.parentElement;
      if (!parent) {
        stack.remove();
        return;
      }
      while (stack.firstChild) {
        parent.insertBefore(stack.firstChild, stack);
      }
      stack.remove();
    });
  }

  function createYoutubeWatchButton() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = YT_WATCH_BTN_ID;
    btn.textContent = '下載解析';
    btn.title = '在 bili2vrc 開啟並獲取格式';
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const liveUrl = youtubeCanonicalUrl(location.href);
      if (!liveUrl) return;
      openInBili2vrc(liveUrl);
    });
    return btn;
  }

  function findActiveShortsReel() {
    const reels = [...document.querySelectorAll('ytd-reel-video-renderer, ytm-shorts-player, ytm-reel-item-renderer')];
    const marked = reels.find((el) => el.hasAttribute('is-active') || el.classList.contains('is-active'));
    if (marked) return marked;
    return reels.find((el) => {
      const rect = el.getBoundingClientRect();
      return (
        rect.height > 120 &&
        rect.top < window.innerHeight * 0.65 &&
        rect.bottom > window.innerHeight * 0.2
      );
    }) || null;
  }

  function findYoutubeShortsLikeHost() {
    const root = findActiveShortsReel() || document;
    return (
      root.querySelector('#like-button') ||
      root.querySelector('like-button-view-model') ||
      root.querySelector('ytd-reel-player-overlay-renderer #like-button') ||
      root.querySelector('ytm-reel-player-overlay-renderer #like-button')
    );
  }

  function mountYoutubeShortsButton(videoUrl) {
    document.getElementById(FIXED_ID)?.remove();
    if (isYoutubeFullscreen()) {
      document.getElementById(YT_WATCH_BTN_ID)?.remove();
      return;
    }

    const likeHost = findYoutubeShortsLikeHost();
    const actions =
      likeHost?.closest('#actions') ||
      findActiveShortsReel()?.querySelector('#actions') ||
      document.querySelector('ytd-reel-player-overlay-renderer #actions');
    if (!likeHost && !actions) return;

    let btn = document.getElementById(YT_WATCH_BTN_ID);
    if (!btn) btn = createYoutubeWatchButton();
    btn.classList.add('b2v-yt-shorts');
    btn.dataset.videoUrl = videoUrl;

    if (likeHost?.parentElement) {
      if (btn.nextElementSibling !== likeHost || btn.parentElement !== likeHost.parentElement) {
        likeHost.parentElement.insertBefore(btn, likeHost);
      }
      return;
    }
    if (btn.parentElement !== actions) {
      actions.prepend(btn);
    }
  }

  function mountYoutubeWatchButton(videoUrl) {
    document.getElementById(FIXED_ID)?.remove();
    unwrapYoutubeThanksStack();
    if (isYoutubeFullscreen()) {
      document.getElementById(YT_WATCH_BTN_ID)?.remove();
      return;
    }

    const likeHost = findYoutubeLikeHost();
    const actionsRow = findYoutubeActionsRow();
    if (!likeHost && !actionsRow) return;

    let btn = document.getElementById(YT_WATCH_BTN_ID);
    if (!btn) btn = createYoutubeWatchButton();
    btn.classList.remove('b2v-yt-shorts');
    btn.dataset.videoUrl = videoUrl;

    if (likeHost?.parentElement) {
      if (btn.nextElementSibling !== likeHost || btn.parentElement !== likeHost.parentElement) {
        likeHost.parentElement.insertBefore(btn, likeHost);
      }
      return;
    }

    if (btn.parentElement !== actionsRow) {
      actionsRow.prepend(btn);
    }
  }

  function ensureWatchPageButton() {
    if (isYouTubeHost()) {
      const videoUrl = youtubeCanonicalUrl(location.href);
      const onWatch =
        location.pathname.includes('/watch') || location.hostname === 'youtu.be';
      const onShorts = location.pathname.includes('/shorts/');
      if (!videoUrl || (!onWatch && !onShorts) || isYoutubeFullscreen()) {
        document.getElementById(FIXED_ID)?.remove();
        document.getElementById(YT_WATCH_BTN_ID)?.remove();
        unwrapYoutubeThanksStack();
        return;
      }
      if (onWatch) {
        mountYoutubeWatchButton(videoUrl);
        return;
      }
      if (onShorts) {
        mountYoutubeShortsButton(videoUrl);
        return;
      }
    }

    const pathBvid = extractBvid(location.pathname + location.search);
    if (!pathBvid || !location.pathname.includes('/video/')) {
      document.getElementById(FIXED_ID)?.remove();
      return;
    }

    let btn = document.getElementById(FIXED_ID);
    if (!btn) {
      btn = document.createElement('button');
      btn.type = 'button';
      btn.id = FIXED_ID;
      btn.textContent = '下載解析';
      btn.title = '在 bili2vrc 開啟並獲取格式';
      // Always resolve BV from the live URL at click time (SPA next-video safe).
      btn.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        const liveBvid = extractBvid(location.pathname + location.search);
        if (!liveBvid) return;
        openInBili2vrc(videoUrlFromBvid(liveBvid));
      });
      (document.body || document.documentElement).appendChild(btn);
    }
    btn.dataset.bvid = pathBvid;
  }

  function isOurNode(node) {
    return (
      node instanceof Element &&
      (node.id === FIXED_ID ||
        node.id === YT_WATCH_BTN_ID ||
        node.classList?.contains(BTN_CLASS) ||
        node.classList?.contains(YT_THANKS_STACK) ||
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
      .pic-box:hover .${BTN_CLASS},
      ytd-thumbnail:hover .${BTN_CLASS},
      ytd-rich-item-renderer:hover .${BTN_CLASS},
      ytd-video-renderer:hover .${BTN_CLASS},
      ytd-grid-video-renderer:hover .${BTN_CLASS},
      ytd-compact-video-renderer:hover .${BTN_CLASS},
      ytd-reel-item-renderer:hover .${BTN_CLASS},
      yt-lockup-view-model:hover .${BTN_CLASS},
      ytm-rich-item-renderer:hover .${BTN_CLASS},
      ytm-media-item:hover .${BTN_CLASS},
      a#thumbnail:hover .${BTN_CLASS},
      a.ytLockupViewModelContentImage:hover .${BTN_CLASS},
      a.ytLockupViewModelHostContentImage:hover .${BTN_CLASS} {
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
      .${YT_THANKS_STACK} {
        display: contents !important;
      }
      #${YT_WATCH_BTN_ID} {
        position: relative !important;
        right: auto !important;
        bottom: auto !important;
        z-index: 3 !important;
        margin: 0 8px 0 0 !important;
        padding: 8px 14px !important;
        border: none !important;
        border-radius: 18px !important;
        background: rgba(236, 72, 153, 0.95) !important;
        color: #fff !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        line-height: 1.2 !important;
        cursor: pointer !important;
        white-space: nowrap !important;
        box-shadow: none !important;
        opacity: 1 !important;
      }
      #${YT_WATCH_BTN_ID}:hover {
        background: rgb(236, 72, 153) !important;
      }
      #${YT_WATCH_BTN_ID}.b2v-yt-shorts {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 48px !important;
        min-width: 48px !important;
        max-width: 64px !important;
        margin: 0 0 12px 0 !important;
        padding: 8px 4px !important;
        border-radius: 24px !important;
        font-size: 12px !important;
        line-height: 1.15 !important;
        white-space: normal !important;
        text-align: center !important;
      }
      body:has(.html5-video-player.ytp-fullscreen) #${FIXED_ID},
      body:has(ytd-watch-flexy[fullscreen]) #${FIXED_ID},
      body:has(ytd-watch-flexy[fullscreen]) #${YT_WATCH_BTN_ID} {
        display: none !important;
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

  // Fixed button immediately; delay / idle cover scans so Bilibili header can mount (4K / jank safe).
  function init() {
    injectStyles();
    registerMenu();
    ensureWatchPageButton();

    let headerQuietUntil = Date.now() + FIRST_SCAN_DELAY_MS;

    const doScan = () => {
      if (Date.now() < headerQuietUntil) return;
      runWhenIdle(() => {
        if (Date.now() < headerQuietUntil) return;
        scanCovers();
        ensureWatchPageButton();
      });
    };

    const rescan = debounce((mutations = []) => {
      if (mutationsAreOurs(mutations)) return;
      // Header mount/teardown often has mutation.target === body; inspect added/removed nodes too.
      // YouTube masthead mutates constantly — still scan, inHeader() skips those nodes.
      if (!isYouTubeHost() && mutationsTouchHeader(mutations)) {
        headerQuietUntil = Date.now() + 1200;
        return;
      }
      doScan();
    }, RESCAN_DEBOUNCE_MS);

    window.setTimeout(() => {
      headerQuietUntil = 0;
      doScan();
    }, FIRST_SCAN_DELAY_MS);

    const observer = new MutationObserver(rescan);
    const observeRoot = () => {
      if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
      }
    };
    if (document.body) {
      observeRoot();
    } else {
      window.addEventListener('DOMContentLoaded', observeRoot, { once: true });
    }

    // Scroll-driven full rescans fight the header on 4K feeds — rely on MutationObserver instead.
    // Keep a light idle rescan after long scrolls for lazy-loaded covers only.
    window.addEventListener('scroll', debounce(() => {
      if (Date.now() < headerQuietUntil) return;
      doScan();
    }, 1200), { passive: true });

    const onSpaNavigate = () => {
      headerQuietUntil = Date.now() + 1000;
      ensureWatchPageButton();
      window.setTimeout(() => {
        headerQuietUntil = 0;
        doScan();
      }, 1000);
    };

    window.addEventListener('yt-navigate-finish', onSpaNavigate);
    document.addEventListener('fullscreenchange', () => ensureWatchPageButton());
    document.addEventListener('webkitfullscreenchange', () => ensureWatchPageButton());

    let lastHref = location.href;
    let lastYoutubeFullscreen = false;
    setInterval(() => {
      if (location.href !== lastHref) {
        lastHref = location.href;
        onSpaNavigate();
      }
      if (!isYouTubeHost()) return;
      const fullscreenNow = isYoutubeFullscreen();
      if (fullscreenNow !== lastYoutubeFullscreen) {
        lastYoutubeFullscreen = fullscreenNow;
        ensureWatchPageButton();
      }
    }, 800);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
