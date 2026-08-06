<script setup lang="ts">
import {
  codecFamilyLabel,
  formatFpsTable,
  formatSize,
  isHdrRange,
} from '~/composables/useFormatUtils'

useHead({
  title: 'bili2vrchat POS — B站→VRChat',
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
    { 'http-equiv': 'Permissions-Policy', content: 'clipboard-read=(self), clipboard-write=(self)' },
  ],
})

const app = reactive(useBili2Vrc())
const cookieFileInput = ref<HTMLInputElement | null>(null)
const previewVideo = ref<HTMLVideoElement | null>(null)
const urlInputEl = ref<HTMLInputElement | null>(null)
const hideCookieWarning = ref(false)
const clockText = ref('')
const pasteWaiting = ref(false)
let pasteWaitCleanup: (() => void) | null = null

let clockTimer: ReturnType<typeof setInterval> | null = null

function updateClock() {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  clockText.value = `${now.getFullYear()}/${pad(now.getMonth() + 1)}/${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

onMounted(() => {
  app.loadHwaccelStatus()
  app.updateCookieWarningForUrl(String(app.urlInput ?? ''))
  updateClock()
  clockTimer = setInterval(updateClock, 1000)

  const incomingUrl = new URL(window.location.href).searchParams.get('url')?.trim()
  if (incomingUrl) {
    app.onUrlInput(incomingUrl)
    void app.fetchFormats(true)
    const cleaned = new URL(window.location.href)
    cleaned.searchParams.delete('url')
    const next = cleaned.pathname + cleaned.search + cleaned.hash
    history.replaceState(null, '', next || '/retro')
  }
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  pasteWaitCleanup?.()
  pasteWaitCleanup = null
})

function onCookieFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    app.uploadCookie(file, true)
    input.value = ''
  }
}

function onUrlKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') app.fetchFormats(true)
}

async function requestClipboardReadPermission(): Promise<'granted' | 'denied' | 'prompt' | 'unknown'> {
  if (!window.isSecureContext || !navigator.permissions?.query) return 'unknown'
  try {
    const status = await navigator.permissions.query({
      name: 'clipboard-read' as PermissionName,
    })
    return status.state as 'granted' | 'denied' | 'prompt'
  } catch {
    return 'unknown'
  }
}

function waitForManualPaste(): Promise<string | null> {
  pasteWaitCleanup?.()
  pasteWaiting.value = true
  urlInputEl.value?.focus()
  urlInputEl.value?.select()

  return new Promise((resolve) => {
    const finish = (value: string | null) => {
      window.clearTimeout(timer)
      window.removeEventListener('paste', onPaste, true)
      window.removeEventListener('keydown', onKey, true)
      pasteWaiting.value = false
      pasteWaitCleanup = null
      resolve(value)
    }
    const onPaste = (event: ClipboardEvent) => {
      const text = event.clipboardData?.getData('text')?.trim() || ''
      if (!text) return
      event.preventDefault()
      finish(text)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') finish(null)
    }
    const timer = window.setTimeout(() => finish(null), 15000)
    pasteWaitCleanup = () => finish(null)
    window.addEventListener('paste', onPaste, true)
    window.addEventListener('keydown', onKey, true)
  })
}

async function pasteAndFetch() {
  if (app.fetchLoading || pasteWaiting.value) return

  let text = ''
  if (window.isSecureContext && navigator.clipboard?.readText) {
    const permission = await requestClipboardReadPermission()
    if (permission !== 'denied') {
      try {
        text = (await navigator.clipboard.readText()).trim()
      } catch {
        /* fall through to Ctrl+V */
      }
    }
  }

  if (!text) {
    text = (await waitForManualPaste()) || ''
    if (!text) return
  }

  app.onUrlInput(text)
  await app.fetchFormats(true)
}

function onPreviewSpeedInput(event: Event) {
  const speed = parseFloat((event.target as HTMLInputElement).value)
  app.onPreviewSpeedChange(speed, previewVideo.value)
}

function onResultVideoLoad() {
  app.onResultVideoLoaded(previewVideo.value)
}

function copyRetroUrl() {
  app.copyUrl(true)
}

const catColorClass = computed(() => {
  const map: Record<string, string> = {
    av1: 'pos-btn-magenta',
    vp9: 'pos-btn-green',
    h264: 'pos-btn-blue',
    h265: 'pos-btn-red',
  }
  return (family: string) => map[family] || 'pos-btn-blue'
})
</script>

<template>
  <div class="retro-app">
    <div class="page-wrap">
      <div class="pos-shell">
        <header class="pos-header">
          <div class="pos-header-title">
            <span class="pos-brand">bili2vrc</span>
            — B站 / YouTube → R2 → VRChat
          </div>
          <div class="pos-header-meta">
            <span>{{ app.statusBarMsg }}</span>
            <span class="pos-clock">{{ clockText }}</span>
            <NuxtLink to="/" class="pos-theme-link">現代版</NuxtLink>
          </div>
        </header>

        <div class="pos-main">
          <!-- Left: check / settings -->
          <aside class="pos-col pos-col-left">
            <div class="pos-col-head">CHECK / 設定</div>
            <div class="pos-col-body">
              <div
                v-if="app.showCookieWarning && !hideCookieWarning"
                class="pos-warn-bar"
              >
                <span>{{ app.cookieWarningText }}</span>
                <button type="button" class="pos-btn" @click="hideCookieWarning = true">關閉</button>
              </div>

              <section class="pos-section">
                <div class="pos-section-title">1. 網址</div>
                <div class="pos-url-row">
                  <input
                    id="posUrl"
                    ref="urlInputEl"
                    class="pos-input"
                    type="text"
                    v-model="app.urlInput"
                    placeholder="bilibili.com/... 或 youtube.com/..."
                    autocomplete="off"
                    spellcheck="false"
                    @input="app.onUrlInput(app.urlInput)"
                    @keydown="onUrlKeydown"
                  >
                  <button
                    type="button"
                    class="pos-btn pos-btn-magenta pos-paste-btn"
                    :disabled="app.fetchLoading || pasteWaiting"
                    @click="pasteAndFetch"
                  >
                    {{ pasteWaiting ? 'Ctrl+V…' : '貼上並解析' }}
                  </button>
                </div>
              </section>

              <section class="pos-section">
                <div class="pos-section-title">2. Cookie</div>
                <input
                  ref="cookieFileInput"
                  class="file-input-hidden"
                  type="file"
                  accept=".txt,text/plain"
                  @change="onCookieFileChange"
                >
                <button
                  class="pos-btn pos-btn-blue pos-btn-block"
                  type="button"
                  @click="cookieFileInput?.click()"
                >
                  Cookie 檔案
                </button>
                <div class="pos-cookie-list">
                  <div
                    v-for="platform in app.COOKIE_PLATFORMS"
                    :key="platform"
                    class="pos-cookie-row"
                    :class="app.cookieStatus[platform] ? 'ok' : 'warn'"
                  >
                    <span>
                      {{ app.platformLabel(platform) }}:
                      {{ app.cookieStatus[platform] ? '已設定' : '未設定' }}
                    </span>
                    <button
                      v-if="app.cookieStatus[platform]"
                      class="pos-btn pos-btn-tiny"
                      type="button"
                      @click="app.clearCookiePlatform(platform, true)"
                    >
                      清除
                    </button>
                  </div>
                </div>
                <div v-if="app.cookieUploadMsg" class="pos-hint">{{ app.cookieUploadMsg }}</div>
              </section>

              <section v-if="app.showVideoMeta" class="pos-section">
                <div class="pos-section-title">影片資訊</div>
                <div class="pos-meta">
                  <img
                    v-if="app.videoMeta?.thumbnail"
                    :src="app.videoMeta.thumbnail"
                    :alt="app.videoMeta.title || '縮圖'"
                    referrerpolicy="no-referrer"
                  >
                  <div>
                    <div class="pos-meta-title">{{ app.videoMeta?.title }}</div>
                    <div class="pos-meta-sub">
                      <div v-if="app.videoMeta?.uploader">UP：{{ app.videoMeta.uploader }}</div>
                      <div v-if="app.videoMeta?.duration_formatted">時長：{{ app.videoMeta.duration_formatted }}</div>
                    </div>
                  </div>
                </div>
              </section>

              <section class="pos-section">
                <div class="pos-section-title">3. 已選項目</div>
                <div class="pos-check-lines">
                  <div class="pos-check-line selected-row">
                    <span>{{ app.selInfoText }}</span>
                  </div>
                  <div class="pos-check-line">
                    <span>格式數</span>
                    <span class="pos-muted">{{ app.retroFmtCountLabel }}</span>
                  </div>
                  <div class="pos-check-line">
                    <span>狀態</span>
                    <span class="pos-muted">{{ app.cookiePanelText }}</span>
                  </div>
                </div>
              </section>

              <section class="pos-section">
                <div class="pos-section-title">4. 上傳設定</div>
                <div class="pos-field">
                  <label class="pos-label" for="keyPhrase">自訂路徑</label>
                  <input
                    id="keyPhrase"
                    class="pos-input"
                    type="text"
                    v-model="app.keyPhrase"
                    placeholder="留空自動隨機"
                    autocomplete="off"
                  >
                </div>
                <div class="pos-field">
                  <label class="pos-label" for="ttlSelect">保存時間</label>
                  <select id="ttlSelect" class="pos-select" v-model="app.ttl">
                    <option :value="3600">1 小時</option>
                    <option :value="86400">1 天</option>
                    <option :value="604800">7 天</option>
                    <option :value="2592000">30 天</option>
                    <option :value="0">永久</option>
                  </select>
                </div>
                <div class="pos-field">
                  <label class="pos-label" for="playbackSpeed">播放速度</label>
                  <select
                    id="playbackSpeed"
                    class="pos-select"
                    :value="app.playbackSpeed"
                    @change="app.playbackSpeed = Number(($event.target as HTMLSelectElement).value)"
                  >
                    <option :value="0.5">0.5x</option>
                    <option :value="0.75">0.75x</option>
                    <option :value="1">1.0x</option>
                    <option :value="1.25">1.25x</option>
                    <option :value="1.5">1.5x</option>
                    <option :value="1.75">1.75x</option>
                    <option :value="2">2.0x</option>
                  </select>
                  <div
                    class="pos-hint"
                    :class="{ 'pos-hint-warn': app.playbackSpeedForcesReencode }"
                  >
                    {{ app.playbackSpeedReencodeWarning }}
                  </div>
                </div>
                <label v-if="app.selectedIsHdr" class="pos-check-label">
                  <input type="checkbox" v-model="app.tonemapHdr">
                  <span>HDR → SDR</span>
                </label>
                <div v-if="app.selectedIsHdr" class="pos-hint">{{ app.tonemapHdrHint }}</div>
              </section>

              <section v-if="app.showAdvancedEncoding" class="pos-section">
                <details class="pos-advanced">
                  <summary>進階編碼</summary>
                  <div class="pos-field">
                    <label class="pos-label" for="encodeMode">編碼模式</label>
                    <select id="encodeMode" class="pos-select" v-model="app.encodeMode">
                      <option
                        v-for="option in app.encodeModeOptions"
                        :key="option.value"
                        :value="option.value"
                      >
                        {{ option.label }}
                      </option>
                    </select>
                  </div>
                  <div v-if="app.selectedIsHdr" class="pos-field">
                    <label class="pos-label" for="tonemapAlgorithm">Mapping</label>
                    <select
                      id="tonemapAlgorithm"
                      class="pos-select"
                      v-model="app.tonemapAlgorithm"
                      :disabled="!app.tonemapHdr"
                    >
                      <option
                        v-for="option in app.tonemapAlgorithmOptions"
                        :key="option.value"
                        :value="option.value"
                      >
                        {{ option.label }}
                      </option>
                    </select>
                    <div class="pos-hint">{{ app.tonemapAlgorithmHint }}</div>
                  </div>
                  <div class="pos-field">
                    <label class="pos-label crf-label-row" for="encodeCrf">
                      <span>{{ app.encodeCrfLabel }}</span>
                      <span class="crf-value">{{ app.encodeCrf }}</span>
                    </label>
                    <input
                      id="encodeCrf"
                      class="crf-slider"
                      type="range"
                      v-model.number="app.encodeCrf"
                      :min="app.encodeCrfConfig.min"
                      :max="app.encodeCrfConfig.max"
                      step="1"
                    >
                    <div class="crf-range-labels">
                      <span>{{ app.crfRangeLabels.low }}</span>
                      <span>{{ app.crfRangeLabels.high }}</span>
                    </div>
                  </div>
                  <div class="pos-field">
                    <label class="pos-label" for="bitrateKbps">{{ app.bitrateFieldLabel }}</label>
                    <select id="bitrateKbps" class="pos-select" v-model.number="app.bitrateKbps">
                      <option
                        v-if="app.bitrateSelectOptions.source"
                        :value="app.bitrateSelectOptions.source"
                      >
                        原始（{{ app.bitrateSelectOptions.source }} kbps）
                      </option>
                      <option
                        v-for="kbps in app.bitrateSelectOptions.presets"
                        :key="kbps"
                        :value="kbps"
                      >
                        {{ kbps }} kbps
                      </option>
                    </select>
                    <div class="pos-hint">
                      {{ app.bitrateFieldHint }}
                      <template v-if="Number(app.playbackSpeed) !== 1 && app.scaleBitrateWithSpeed">
                        。倍速實際{{ app.encodeMode === 'cbr' ? '目標' : '上限' }}
                        {{ app.bitrateCeilingKbps }} kbps
                      </template>
                    </div>
                  </div>
                  <div class="pos-hint">{{ app.hwEncoderLabel }}</div>
                </details>
              </section>

              <section
                v-if="app.showProgressBar || app.showStatusBox || app.showResultBox"
                class="pos-section"
              >
                <div class="pos-section-title">進度 / 結果</div>
                <div v-if="app.showProgressBar" class="pos-progress">
                  <div class="pos-progress-fill" />
                </div>
                <div v-if="app.showStatusBox" class="pos-status-box">
                  {{ app.statusMsg }}
                </div>
                <div v-if="app.showResultBox" class="pos-result">
                  <div class="pos-result-title">上傳完成 — VRChat 直連</div>
                  <div class="pos-result-row">
                    <input class="pos-result-url" type="text" readonly :value="app.resultUrl">
                    <button type="button" class="pos-btn pos-btn-green" @click="copyRetroUrl">
                      {{ app.copyBtnText }}
                    </button>
                  </div>
                  <video
                    ref="previewVideo"
                    :key="app.resultUrl"
                    controls
                    playsinline
                    preload="metadata"
                    :src="app.resultUrl"
                    @loadeddata="onResultVideoLoad"
                  />
                  <div class="preview-speed">
                    <label for="previewSpeed">預覽</label>
                    <input
                      id="previewSpeed"
                      type="range"
                      min="0.5"
                      max="2"
                      step="0.05"
                      :value="app.previewSpeed"
                      @input="onPreviewSpeedInput"
                    >
                    <span>{{ app.previewSpeed.toFixed(2) }}x</span>
                  </div>
                </div>
              </section>
            </div>
          </aside>

          <!-- Center: format item grid -->
          <section class="pos-col pos-col-center">
            <div class="pos-col-head">
              格式選單
              <span style="font-weight:normal;margin-left:6px">{{ app.retroFmtCountLabel }}</span>
            </div>
            <div class="pos-items">
              <div
                v-if="app.fmtTableMessage"
                class="pos-empty"
                :class="{ error: app.fmtTableError }"
              >
                {{ app.fmtTableMessage }}
              </div>
              <button
                v-for="(format, index) in app.filteredFormats"
                :key="format.format_id"
                type="button"
                class="pos-btn pos-item"
                :class="{ selected: app.selectedIdx === index }"
                @click="app.selectFormat(index)"
              >
                <span class="pos-item-name">{{ format.resolution }}</span>
                <span class="pos-item-sub">
                  <span :class="{ 'pos-item-hdr': isHdrRange(format.dynamic_range) }">
                    {{ format.dynamic_range || 'SDR' }}
                  </span>
                  · {{ formatFpsTable(format.fps) }}
                  · {{ format.codec }}
                </span>
                <span class="pos-item-price">{{ formatSize(format) }}</span>
              </button>
            </div>
          </section>

          <!-- Right: categories -->
          <aside class="pos-col pos-col-right">
            <div class="pos-col-head">編碼分類</div>
            <div class="pos-col-body">
              <section class="pos-section">
                <div class="pos-section-title">來源編碼</div>
                <div class="pos-cats">
                  <button
                    v-for="family in app.codecFamilies"
                    :key="family"
                    type="button"
                    class="pos-btn pos-cat"
                    :class="[catColorClass(family), { active: app.codecFamily === family }]"
                    :disabled="app.codecFamilies.length <= 1"
                    @click="app.setCodecFamily(family)"
                  >
                    {{ codecFamilyLabel(family) }}
                  </button>
                  <div v-if="!app.codecFamilies.length" class="pos-hint" style="margin:6px">
                    取得格式後顯示
                  </div>
                </div>
              </section>

              <section class="pos-section">
                <div class="pos-section-title">輸出模式</div>
                <div class="pos-cats">
                  <button
                    v-for="option in app.outputModeOptions"
                    :key="option.value"
                    type="button"
                    class="pos-btn pos-cat"
                    :class="{
                      active: app.outputMode === option.value,
                      'pos-btn-green': option.value === 'original',
                      'pos-btn-magenta': option.value === 'av1',
                      'pos-btn-blue': option.value === 'h264',
                    }"
                    :disabled="option.value === 'original' && app.originalModeDisabled"
                    @click="app.setOutputMode(option.value)"
                  >
                    {{ option.label }}
                  </button>
                  <div class="pos-hint" style="margin:6px">{{ app.outputModeHint }}</div>
                </div>
              </section>
            </div>
          </aside>
        </div>

        <footer class="pos-footer">
          <button
            type="button"
            class="pos-btn pos-btn-blue"
            :disabled="app.fetchLoading"
            @click="app.fetchFormats(true)"
          >
            {{ app.fetchLoading ? '載入中…' : '獲取格式' }}
          </button>
          <button
            type="button"
            class="pos-btn pos-btn-red"
            :disabled="!app.selectedFormat || app.processLoading"
            @click="app.startProcess(true)"
          >
            {{ app.processLoading ? '處理中…' : '下載並上傳' }}
          </button>
          <button
            type="button"
            class="pos-btn pos-btn-green"
            :disabled="!app.showCancelBtn || app.cancelBtnDisabled"
            @click="app.cancelProcess(true)"
          >
            取消
          </button>
          <div class="pos-footer-note">
            先選右欄編碼 → 中欄解析度 → 左欄設定 → 下載並上傳
          </div>
        </footer>
      </div>

      <div class="page-footer">
        POS 復古介面 · bili2vrchat · B站→Cloudflare R2→VRChat
      </div>
    </div>
  </div>
</template>

<style>
@import "~/assets/css/retro.css";

/* Force POS visual partitions (survives if src import is flaky) */
.retro-app {
  --pos-paper: #d4c4a8;
  --pos-ink: #1a1208;
  --pos-header: #8b1515;
  --pos-accent-yellow: #ffe14a;
  --pos-blue: #0a2f9e;
  --pos-red: #b01010;
  --pos-green: #0a6b1c;
  --pos-magenta: #8b0a7a;
  --pos-border: #3a3020;
  --pos-bevel-light: #f4ebe0;
  --pos-bevel-dark: #6a5a40;
  --pos-btn-face: #e8dcc8;
  --pos-panel: #dccdb4;
  color: var(--pos-ink);
  font-family: Tahoma, Verdana, "MS Sans Serif", Arial, sans-serif;
  font-size: 15px;
  background: #2a2218;
  min-height: 100vh;
  padding: 8px;
  box-sizing: border-box;
}

.retro-app *,
.retro-app *::before,
.retro-app *::after {
  box-sizing: border-box;
}

.retro-app .pos-shell {
  background: var(--pos-paper) !important;
  border: 2px solid var(--pos-border) !important;
  box-shadow: 3px 3px 0 #1a1208;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 40px);
}

.retro-app .pos-header {
  background: var(--pos-header) !important;
  color: #fff8e8 !important;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 2px solid #4a0808;
  font-size: 15px;
}

.retro-app .pos-brand,
.retro-app .pos-clock,
.retro-app .pos-theme-link {
  color: #ffe14a !important;
  font-weight: bold;
}

.retro-app .pos-main {
  display: flex !important;
  flex-direction: row !important;
  flex-wrap: nowrap !important;
  width: 100%;
  flex: 1;
  border-bottom: 2px solid var(--pos-border);
}

.retro-app .pos-col {
  background: var(--pos-panel) !important;
  border-right: 2px solid var(--pos-border) !important;
  min-height: 420px;
  max-height: calc(100vh - 140px);
  overflow: auto;
}

.retro-app .pos-col-left {
  flex: 0 0 34% !important;
  max-width: 420px;
  min-width: 280px;
}

.retro-app .pos-col-center {
  flex: 1 1 auto !important;
  min-width: 0;
}

.retro-app .pos-col-right {
  flex: 0 0 200px !important;
  min-width: 180px;
  border-right: none !important;
}

.retro-app .pos-col-head {
  background: #b8a888 !important;
  border-bottom: 2px solid var(--pos-border) !important;
  padding: 10px 12px;
  font-weight: bold;
  font-size: 16px;
  color: var(--pos-ink);
}

.retro-app .pos-col-body {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.retro-app .pos-section {
  border: 2px solid var(--pos-border) !important;
  background: #efe4ce !important;
  padding: 0;
  margin: 0;
}

.retro-app .pos-section-title {
  background: #c4b090 !important;
  border-bottom: 1px solid var(--pos-border);
  padding: 8px 10px;
  font-weight: bold;
  font-size: 14px;
  color: var(--pos-ink);
}

.retro-app .pos-section > .pos-url-row,
.retro-app .pos-section > .pos-field,
.retro-app .pos-section > .pos-hint,
.retro-app .pos-section > .pos-check-label,
.retro-app .pos-section > .pos-btn,
.retro-app .pos-section > .pos-cookie-list,
.retro-app .pos-section > .pos-meta,
.retro-app .pos-section > .pos-check-lines,
.retro-app .pos-section > .pos-advanced,
.retro-app .pos-section > .pos-progress,
.retro-app .pos-section > .pos-status-box,
.retro-app .pos-section > .pos-result {
  margin: 8px;
}

.retro-app .pos-url-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.retro-app .pos-url-row .pos-input {
  flex: 1;
  min-width: 0;
}

.retro-app .pos-paste-btn {
  flex: 0 0 auto;
  min-width: 120px;
  white-space: nowrap;
}

.retro-app .pos-btn {
  appearance: none;
  background: var(--pos-btn-face) !important;
  border: 2px solid !important;
  border-color: var(--pos-bevel-light) var(--pos-bevel-dark) var(--pos-bevel-dark) var(--pos-bevel-light) !important;
  color: var(--pos-ink);
  font-family: inherit;
  font-size: 15px;
  font-weight: bold;
  padding: 12px 14px;
  min-height: 48px;
  cursor: pointer;
  border-radius: 0 !important;
}

.retro-app .pos-btn:active:not(:disabled) {
  border-color: var(--pos-bevel-dark) var(--pos-bevel-light) var(--pos-bevel-light) var(--pos-bevel-dark) !important;
}

.retro-app .pos-btn:disabled {
  color: #777 !important;
  cursor: default;
}

.retro-app .pos-btn-block { width: 100%; }
.retro-app .pos-btn-tiny {
  font-size: 13px;
  padding: 8px 12px;
  min-height: 40px;
}
.retro-app .pos-btn-blue { color: var(--pos-blue) !important; }
.retro-app .pos-btn-red { color: var(--pos-red) !important; }
.retro-app .pos-btn-green { color: var(--pos-green) !important; }
.retro-app .pos-btn-magenta { color: var(--pos-magenta) !important; }

.retro-app .pos-btn.active,
.retro-app .pos-cat.active,
.retro-app .pos-item.selected {
  background: var(--pos-accent-yellow) !important;
  box-shadow: inset 0 0 0 2px var(--pos-border);
}

.retro-app .pos-input,
.retro-app .pos-select {
  width: 100%;
  font-family: inherit;
  font-size: 15px;
  padding: 10px 12px;
  min-height: 48px;
  border: 2px solid !important;
  border-color: var(--pos-bevel-dark) var(--pos-bevel-light) var(--pos-bevel-light) var(--pos-bevel-dark) !important;
  background: #fffef8 !important;
  color: var(--pos-ink);
  border-radius: 0 !important;
}

.retro-app .pos-label {
  display: block;
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 4px;
}

.retro-app .pos-hint {
  font-size: 13px;
  color: #5a4a30;
  line-height: 1.4;
}

.retro-app .pos-hint-warn {
  color: var(--pos-red) !important;
  font-weight: bold;
}

.retro-app .pos-check-lines {
  border: 1px solid var(--pos-border);
  background: #fff8e8;
}

.retro-app .pos-check-line {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 8px;
  border-bottom: 1px dotted #a89878;
  font-size: 14px;
  color: var(--pos-blue);
}

.retro-app .pos-check-line:last-child { border-bottom: none; }

.retro-app .pos-check-line.selected-row {
  background: var(--pos-accent-yellow) !important;
  color: var(--pos-ink) !important;
  font-weight: bold;
}

.retro-app .pos-cookie-list {
  margin: 6px;
}

.retro-app .pos-cookie-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  padding: 6px 0;
}

.retro-app .pos-cookie-row.ok { color: var(--pos-green); }
.retro-app .pos-cookie-row.warn { color: var(--pos-red); }

.retro-app .pos-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  padding: 10px;
}

.retro-app .pos-item {
  position: relative;
  min-height: 96px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 8px 22px;
  color: var(--pos-blue) !important;
  font-size: 15px;
}

.retro-app .pos-item-name {
  font-size: 16px;
  font-weight: bold;
}

.retro-app .pos-item-sub {
  font-size: 12px;
  margin-top: 4px;
}

.retro-app .pos-item-price {
  position: absolute;
  right: 6px;
  bottom: 4px;
  font-size: 13px;
  color: var(--pos-ink);
}

.retro-app .pos-empty {
  grid-column: 1 / -1;
  padding: 32px 14px;
  text-align: center;
  border: 2px dashed var(--pos-border);
  background: #efe4ce;
  color: #5a4a30;
  font-size: 15px;
}

.retro-app .pos-cats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.retro-app .pos-cat {
  min-height: 56px;
  width: 100%;
  font-size: 15px;
}

.retro-app .pos-cat-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 2px solid var(--pos-border);
}

.retro-app .pos-cat-label {
  font-size: 10px;
  font-weight: bold;
  margin-bottom: 4px;
  color: #5a4a30;
}

.retro-app .pos-footer {
  display: grid !important;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  padding: 12px;
  background: #c8b898 !important;
  border-top: 2px solid var(--pos-bevel-light);
}

.retro-app .pos-footer .pos-btn {
  min-height: 64px;
  font-size: 18px;
}

.retro-app .pos-footer-note {
  grid-column: 1 / -1;
  text-align: center;
  font-size: 13px;
  color: #5a4a30;
}

.retro-app .pos-check-label {
  font-size: 15px;
  min-height: 44px;
  gap: 10px;
}

.retro-app .pos-check-label input[type="checkbox"] {
  width: 22px;
  height: 22px;
}

.retro-app .crf-slider {
  min-height: 36px;
}

.retro-app .page-footer {
  text-align: center;
  color: #c8b090;
  font-size: 10px;
  margin-top: 8px;
}

.retro-app .file-input-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
}

@media (max-width: 640px) {
  .retro-app .pos-main {
    flex-direction: column !important;
  }

  .retro-app .pos-col-left,
  .retro-app .pos-col-center,
  .retro-app .pos-col-right {
    flex: 1 1 auto !important;
    max-width: none !important;
    width: 100% !important;
    border-right: none !important;
    border-bottom: 2px solid var(--pos-border);
  }
}
</style>
