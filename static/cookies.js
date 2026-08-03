/**
 * Browser-side cookie cache (localStorage) for bilibili / youtube.
 */
const CookieStore = (() => {
  const STORAGE_KEY = 'bili2vrchat_cookies';
  const PLATFORMS = ['bilibili', 'youtube'];

  function loadStore() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch (_) {
      return {};
    }
  }

  function saveStore(store) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  }

  function detectPlatformFromUrl(url) {
    try {
      const host = new URL(url).hostname.toLowerCase();
      if (host.includes('bilibili.com') || host.endsWith('b23.tv')) {
        return 'bilibili';
      }
      if (host.includes('youtube.com') || host === 'youtu.be' || host.endsWith('.youtu.be')) {
        return 'youtube';
      }
    } catch (_) {}
    return null;
  }

  function domainMatchesPlatform(domain, platform) {
    const host = domain.toLowerCase().replace(/^\./, '');
    if (platform === 'bilibili') {
      return host.includes('bilibili.com') || host.endsWith('b23.tv');
    }
    if (platform === 'youtube') {
      return host.includes('youtube.com') || host === 'youtu.be' || host.endsWith('.youtu.be');
    }
    return false;
  }

  function detectPlatformsFromCookieContent(content) {
    const found = new Set();
    for (const line of content.split(/\r?\n/)) {
      const stripped = line.trim();
      if (!stripped || stripped.startsWith('#')) continue;
      if (!stripped.includes('\t')) continue;
      const domain = stripped.split('\t', 1)[0];
      for (const platform of PLATFORMS) {
        if (domainMatchesPlatform(domain, platform)) {
          found.add(platform);
        }
      }
    }
    return found;
  }

  function saveCookie(platform, content, filename) {
    const store = loadStore();
    store[platform] = {
      content,
      filename: filename || 'cookies.txt',
      savedAt: Math.floor(Date.now() / 1000),
    };
    saveStore(store);
  }

  function saveCookieFromFile(content, filename) {
    const platforms = detectPlatformsFromCookieContent(content);
    if (!platforms.size) {
      return {
        ok: false,
        error: '無法辨識 cookie 所屬網站（需包含 bilibili.com 或 youtube.com 域名）',
      };
    }
    for (const platform of platforms) {
      saveCookie(platform, content, filename);
    }
    const labels = [...platforms].map(p => p === 'bilibili' ? 'Bilibili' : 'YouTube');
    return { ok: true, platforms: [...platforms], message: `已儲存 ${labels.join(' + ')} cookie` };
  }

  function getCookie(platform) {
    const store = loadStore();
    return store[platform] || null;
  }

  function clearCookie(platform) {
    const store = loadStore();
    delete store[platform];
    saveStore(store);
  }

  function getCookieStatus() {
    const store = loadStore();
    return {
      bilibili: Boolean(store.bilibili),
      youtube: Boolean(store.youtube),
    };
  }

  function getCookieForUrl(url) {
    const platform = detectPlatformFromUrl(url);
    if (!platform) return null;
    const entry = getCookie(platform);
    return entry ? entry.content : null;
  }

  function platformLabel(platform) {
    return platform === 'bilibili' ? 'Bilibili' : 'YouTube';
  }

  return {
    PLATFORMS,
    detectPlatformFromUrl,
    detectPlatformsFromCookieContent,
    saveCookieFromFile,
    getCookie,
    clearCookie,
    getCookieStatus,
    getCookieForUrl,
    platformLabel,
  };
})();
