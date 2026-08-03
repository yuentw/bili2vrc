const STORAGE_KEY = 'bili2vrchat_cookies'
export const COOKIE_PLATFORMS = ['bilibili', 'youtube'] as const
export type CookiePlatform = (typeof COOKIE_PLATFORMS)[number]

interface CookieEntry {
  content: string
  filename: string
  savedAt: number
}

type CookieStore = Partial<Record<CookiePlatform, CookieEntry>>

function loadStore(): CookieStore {
  if (!import.meta.client) return {}
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveStore(store: CookieStore) {
  if (!import.meta.client) return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store))
}

function domainMatchesPlatform(domain: string, platform: CookiePlatform): boolean {
  const host = domain.toLowerCase().replace(/^\./, '')
  if (platform === 'bilibili') {
    return host.includes('bilibili.com') || host.endsWith('b23.tv')
  }
  if (platform === 'youtube') {
    return host.includes('youtube.com') || host === 'youtu.be' || host.endsWith('.youtu.be')
  }
  return false
}

export function detectPlatformFromUrl(url: string | undefined): CookiePlatform | null {
  if (!url) return null
  try {
    const host = new URL(url).hostname.toLowerCase()
    if (host.includes('bilibili.com') || host.endsWith('b23.tv')) {
      return 'bilibili'
    }
    if (host.includes('youtube.com') || host === 'youtu.be' || host.endsWith('.youtu.be')) {
      return 'youtube'
    }
  } catch {
    /* invalid URL */
  }
  return null
}

export function detectPlatformsFromCookieContent(content: string): Set<CookiePlatform> {
  const found = new Set<CookiePlatform>()
  for (const line of content.split(/\r?\n/)) {
    const stripped = line.trim()
    if (!stripped || stripped.startsWith('#')) continue
    if (!stripped.includes('\t')) continue
    const domain = stripped.split('\t', 1)[0]
    for (const platform of COOKIE_PLATFORMS) {
      if (domainMatchesPlatform(domain, platform)) {
        found.add(platform)
      }
    }
  }
  return found
}

export function platformLabel(platform: CookiePlatform): string {
  return platform === 'bilibili' ? 'Bilibili' : 'YouTube'
}

export function useCookieStore() {
  const cookieStatus = ref<Record<CookiePlatform, boolean>>({
    bilibili: false,
    youtube: false,
  })
  const cookieUploadMsg = ref('')
  const cookieWarningText = ref('')
  const showCookieWarning = ref(false)

  function refreshCookieStatus() {
    const store = loadStore()
    cookieStatus.value = {
      bilibili: Boolean(store.bilibili),
      youtube: Boolean(store.youtube),
    }
  }

  function updateCookieWarningForUrl(url: string | undefined) {
    const platform = detectPlatformFromUrl((url ?? '').trim())
    if (!platform) {
      showCookieWarning.value = false
      return
    }
    const hasCookie = cookieStatus.value[platform]
    showCookieWarning.value = !hasCookie
    if (!hasCookie) {
      cookieWarningText.value =
        `⚠ 此 ${platformLabel(platform)} 網址可能需要 cookie，請上傳 cookies.txt（依檔案內容自動辨識平台）`
    }
  }

  function getCookieForUrl(url: string): string | null {
    const platform = detectPlatformFromUrl(url)
    if (!platform) return null
    const store = loadStore()
    const entry = store[platform]
    return entry ? entry.content : null
  }

  function buildRequestBody(url: string, extra: Record<string, unknown> = {}) {
    const body: Record<string, unknown> = { url, ...extra }
    const cookieContent = getCookieForUrl(url)
    if (cookieContent) body.cookie_content = cookieContent
    return body
  }

  function saveCookieFromFile(content: string, filename: string) {
    const platforms = detectPlatformsFromCookieContent(content)
    if (!platforms.size) {
      return {
        ok: false as const,
        error: '無法辨識 cookie 所屬網站（需包含 bilibili.com 或 youtube.com 域名）',
      }
    }
    const store = loadStore()
    for (const platform of platforms) {
      store[platform] = {
        content,
        filename: filename || 'cookies.txt',
        savedAt: Math.floor(Date.now() / 1000),
      }
    }
    saveStore(store)
    refreshCookieStatus()
    const labels = [...platforms].map((p) => platformLabel(p))
    return {
      ok: true as const,
      platforms: [...platforms],
      message: `已儲存 ${labels.join(' + ')} cookie`,
    }
  }

  function clearCookie(platform: CookiePlatform) {
    const store = loadStore()
    delete store[platform]
    saveStore(store)
    refreshCookieStatus()
    cookieUploadMsg.value = `已清除 ${platformLabel(platform)} cookie`
  }

  if (import.meta.client) {
    refreshCookieStatus()
  }

  return {
    COOKIE_PLATFORMS,
    cookieStatus,
    cookieUploadMsg,
    cookieWarningText,
    showCookieWarning,
    refreshCookieStatus,
    updateCookieWarningForUrl,
    getCookieForUrl,
    buildRequestBody,
    saveCookieFromFile,
    clearCookie,
    platformLabel,
  }
}
