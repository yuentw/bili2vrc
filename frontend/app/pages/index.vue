<script setup lang="ts">
import {
  codecFamilyLabel,
  formatFpsTable,
  formatFpsLabel,
  formatSize,
  getCodecClass,
  isHdrRange,
} from '~/composables/useFormatUtils'

useHead({
  title: 'bili2vrchat — B站上傳工具',
  link: [
    { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
    { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
    {
      rel: 'stylesheet',
      href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@400;500&display=swap',
    },
  ],
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
    { 'http-equiv': 'Permissions-Policy', content: 'clipboard-read=(self), clipboard-write=(self)' },
  ],
})

const app = reactive(useBili2Vrc())
const cookieFileInput = ref<HTMLInputElement | null>(null)
const previewVideo = ref<HTMLVideoElement | null>(null)
const urlInputEl = ref<HTMLInputElement | null>(null)
const pasteWaiting = ref(false)
let pasteWaitCleanup: (() => void) | null = null

onMounted(() => {
  app.loadHwaccelStatus()
  app.updateCookieWarningForUrl(String(app.urlInput ?? ''))

  const incomingUrl = new URL(window.location.href).searchParams.get('url')?.trim()
  if (incomingUrl) {
    app.onUrlInput(incomingUrl)
    void app.fetchFormats()
    const cleaned = new URL(window.location.href)
    cleaned.searchParams.delete('url')
    const next = cleaned.pathname + cleaned.search + cleaned.hash
    history.replaceState(null, '', next || '/')
  }
})

onBeforeUnmount(() => {
  pasteWaitCleanup?.()
  pasteWaitCleanup = null
})

function onCookieFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    app.uploadCookie(file)
    input.value = ''
  }
}

function onUrlKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') app.fetchFormats()
}

async function requestClipboardReadPermission(): Promise<'granted' | 'denied' | 'prompt' | 'unknown'> {
  if (!window.isSecureContext || !navigator.permissions?.query) return 'unknown'
  try {
    const status = await navigator.permissions.query({
      name: 'clipboard-read' as PermissionName,
    })
    return status.state as 'granted' | 'denied' | 'prompt'
  } catch {
    // Firefox / Safari may not expose clipboard-read in Permissions API.
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
        // Triggers the browser clipboard permission prompt when state is "prompt".
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
  await app.fetchFormats()
}

function onPreviewSpeedInput(event: Event) {
  const speed = parseFloat((event.target as HTMLInputElement).value)
  app.onPreviewSpeedChange(speed, previewVideo.value)
}

function onResultVideoLoad() {
  app.onResultVideoLoaded(previewVideo.value)
}
</script>

<template>
  <div class="main-app">
    <div class="grain" aria-hidden="true" />

    <header class="site-header">
      <div class="header-brand">
        <span class="header-eyebrow">upload terminal</span>
        <h1>bili2vrchat</h1>
        <p class="header-tagline">B站 / YouTube → R2 → VRChat</p>
      </div>
      <!-- <NuxtLink to="/retro" class="header-link">Windows XP 版</NuxtLink> -->
    </header>

    <main class="workspace">
      <aside class="col-side">
      <div class="section section-workflow">
        <div class="section-title">操作流程</div>
        <div class="section-body">
          <div class="url-row">
            <input
              ref="urlInputEl"
              type="text"
              v-model="app.urlInput"
              placeholder="B站或 YouTube 網址"
              autocomplete="off"
              spellcheck="false"
              @input="app.onUrlInput(app.urlInput)"
              @keydown="onUrlKeydown"
            >
            <div class="url-actions">
              <button
                class="btn btn-ghost"
                type="button"
                :disabled="app.fetchLoading"
                @click="pasteAndFetch"
              >
                {{ pasteWaiting ? 'Ctrl+V…' : '貼上' }}
              </button>
              <button
                class="btn btn-primary"
                :disabled="app.fetchLoading"
                @click="app.fetchFormats()"
              >
                {{ app.fetchLoading ? '載入中...' : '獲取格式' }}
              </button>
            </div>
          </div>
          <div
            v-if="app.showCookieWarning"
            id="cookieWarning"
            style="display: block"
          >
            {{ app.cookieWarningText }}
          </div>
          <div class="cookie-row">
            <input
              ref="cookieFileInput"
              class="file-input-hidden"
              type="file"
              accept=".txt,text/plain"
              @change="onCookieFileChange"
            >
            <button
              class="btn btn-ghost cookie-file-picker btn-sm"
              type="button"
              @click="cookieFileInput?.click()"
            >
              cookies.txt
            </button>
            <div class="cookie-platforms">
              <div
                v-for="platform in app.COOKIE_PLATFORMS"
                :key="platform"
                class="cookie-platform-row"
                :class="app.cookieStatus[platform] ? 'ok' : 'warn'"
              >
                <span>
                  {{ app.platformLabel(platform) }}:
                  {{ app.cookieStatus[platform] ? '✓' : '—' }}
                </span>
                <button
                  v-if="app.cookieStatus[platform]"
                  class="btn btn-ghost btn-xs"
                  type="button"
                  @click="app.clearCookiePlatform(platform)"
                >
                  清除
                </button>
              </div>
            </div>
          </div>
          <div v-if="app.cookieUploadMsg" id="cookieUploadMsg">{{ app.cookieUploadMsg }}</div>

          <div class="options-grid">
            <div class="options-row-2">
              <div class="field">
                <label>路徑名稱</label>
                <input type="text" v-model="app.keyPhrase" placeholder="留空隨機" autocomplete="off">
              </div>
              <div class="field">
                <label>保存時間</label>
                <select v-model="app.ttl">
                  <option :value="3600">1 小時</option>
                  <option :value="86400">1 天</option>
                  <option :value="604800">7 天</option>
                  <option :value="2592000">30 天</option>
                  <option :value="0">永久</option>
                </select>
              </div>
            </div>
            <div class="field">
              <label>播放速度（上傳前處理）</label>
              <select
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
                v-if="app.playbackSpeedForcesReencode"
                class="field-hint field-hint-warn"
              >
                {{ app.playbackSpeedReencodeWarning }}
              </div>
            </div>

            <div class="action-bar">
              <div class="action-bar-buttons">
                <button
                  class="btn btn-primary btn-upload"
                  :disabled="!app.selectedFormat || app.processLoading"
                  @click="app.startProcess()"
                >
                  下載並上傳
                </button>
                <button
                  v-if="app.showCancelBtn"
                  class="btn btn-ghost"
                  id="cancelBtn"
                  :disabled="app.cancelBtnDisabled"
                  @click="app.cancelProcess()"
                >
                  取消
                </button>
              </div>
              <div id="selInfo">
                <template v-if="app.selectedFormat">
                  已選 <span>{{ app.selectedFormat.resolution }}</span>
                  {{ app.selectedFormat.codec }}
                  {{ formatFpsLabel(app.selectedFormat.fps) }}
                </template>
                <template v-else>先在右側選擇格式</template>
              </div>
            </div>

            <div class="field field-full">
              <label>輸出模式</label>
              <div class="codec-btn-group output-mode-group" role="group" aria-label="輸出模式">
                <button
                  v-for="option in app.outputModeOptions"
                  :key="option.value"
                  type="button"
                  class="codec-btn"
                  :class="{ active: app.outputMode === option.value }"
                  :disabled="option.value === 'original' && app.originalModeDisabled"
                  @click="app.setOutputMode(option.value)"
                >
                  {{ option.label }}
                </button>
              </div>
              <div class="field-hint">{{ app.outputModeHint }}</div>
            </div>
            <div v-if="app.selectedIsHdr" class="field field-full">
              <label class="compat-check">
                <input type="checkbox" v-model="app.tonemapHdr">
                <span>HDR → SDR（tonemap）</span>
              </label>
              <div class="field-hint">{{ app.tonemapHdrHint }}</div>
            </div>
          </div>

          <details v-if="app.showAdvancedEncoding" class="advanced-options">
            <summary>進階編碼選項</summary>
            <div class="options-grid advanced-options-body">
              <div class="field">
                <label>編碼模式（重新編碼時）</label>
                <select v-model="app.encodeMode">
                  <option
                    v-for="option in app.encodeModeOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </div>
              <div v-if="app.selectedIsHdr" class="field">
                <label>Mapping（HDR→SDR）</label>
                <select v-model="app.tonemapAlgorithm" :disabled="!app.tonemapHdr">
                  <option
                    v-for="option in app.tonemapAlgorithmOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
                <div class="field-hint">{{ app.tonemapAlgorithmHint }}</div>
              </div>
              <div class="field">
                <label class="crf-label-row">
                  <span>{{ app.encodeCrfLabel }}</span>
                  <span class="crf-value">{{ app.encodeCrf }}</span>
                </label>
                <input
                  type="range"
                  class="crf-slider"
                  v-model.number="app.encodeCrf"
                  :min="app.encodeCrfConfig.min"
                  :max="app.encodeCrfConfig.max"
                  step="1"
                >
                <div class="crf-range-labels">
                  <span>{{ app.crfRangeLabels.low }}</span>
                  <span>{{ app.crfRangeLabels.high }}</span>
                </div>
                <div class="field-hint">{{ app.encodeCrfConfig.hint }}</div>
              </div>
              <div class="field">
                <label>{{ app.bitrateFieldLabel }}</label>
                <select v-model.number="app.bitrateKbps">
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
                <div class="field-hint">
                  {{ app.bitrateFieldHint }}
                  <template v-if="Number(app.playbackSpeed) !== 1 && app.scaleBitrateWithSpeed">
                    。倍速實際{{ app.encodeMode === 'cbr' ? '目標' : '上限' }}
                    {{ app.bitrateCeilingKbps }} kbps（選取值 × {{ app.playbackSpeed }}x）
                  </template>
                </div>
              </div>
              <div class="field field-full">
                <div id="hwEncoderLabel">{{ app.hwEncoderLabel }}</div>
              </div>
            </div>
          </details>
        </div>
      </div>

      <div v-if="app.showStatusBox" id="statusBox" style="display: block">
        <div class="status-row">
          <div class="step-dot" :class="app.statusDotClass" id="stepDot" />
          <div id="statusMsg">{{ app.statusMsg }}</div>
        </div>
      </div>

      <div v-if="app.showResultBox" id="resultBox" style="display: block">
        <div class="result-label">✓ 上傳完成 — VRChat 直連</div>
        <div class="result-link-row">
          <div id="resultUrl">{{ app.resultUrl }}</div>
          <button class="btn btn-ghost" id="copyBtn" @click="app.copyUrl()">{{ app.copyBtnText }}</button>
        </div>
        <video
          ref="previewVideo"
          id="previewVideo"
          :key="app.resultUrl"
          controls
          playsinline
          preload="metadata"
          :src="app.resultUrl"
          @loadeddata="onResultVideoLoad"
        />
        <div class="preview-speed">
          <label for="previewSpeed">預覽速度</label>
          <input
            id="previewSpeed"
            type="range"
            min="0.5"
            max="2"
            step="0.05"
            :value="app.previewSpeed"
            @input="onPreviewSpeedInput"
          >
          <span id="previewSpeedLabel">{{ app.previewSpeed.toFixed(2) }}x</span>
        </div>
        <div class="vrchat-hint">💡 在 VRChat 影片播放器中貼上此連結即可播放</div>
      </div>
      </aside>

      <div class="col-main">
      <div v-if="app.showVideoMeta" id="videoMeta" style="display: block">
        <div class="video-meta-inner">
          <img
            v-if="app.videoMeta?.thumbnail"
            id="videoThumb"
            :src="app.videoMeta.thumbnail"
            :alt="app.videoMeta.title || '影片縮圖'"
            referrerpolicy="no-referrer"
          >
          <div class="video-meta-text">
            <div id="videoTitle">{{ app.videoMeta?.title }}</div>
            <div class="video-meta-sub">
              <div v-if="app.videoMeta?.uploader" id="videoUploader">
                UP主：{{ app.videoMeta.uploader }}
              </div>
              <div v-if="app.videoMeta?.duration_formatted" id="videoDuration">
                時長：{{ app.videoMeta.duration_formatted }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="section section-formats">
        <div class="section-title fmt-header">
          <span>格式列表 <span id="fmtCount" class="fmt-count">{{ app.fmtCountLabel }}</span></span>
          <div class="codec-filter-group">
            <span class="codec-filter-label">編碼</span>
            <div class="codec-btn-group" role="group" aria-label="編碼篩選">
              <button
                v-for="family in app.codecFamilies"
                :key="family"
                type="button"
                class="codec-btn"
                :class="{ active: app.codecFamily === family }"
                :disabled="app.codecFamilies.length <= 1"
                @click="app.setCodecFamily(family)"
              >
                {{ codecFamilyLabel(family) }}
              </button>
            </div>
          </div>
        </div>
        <div class="table-wrap">
          <table id="fmtTable">
            <thead>
              <tr>
                <th>解析度</th>
                <th>範圍</th>
                <th>FPS</th>
                <th>編碼</th>
                <th class="right">大小</th>
              </tr>
            </thead>
            <tbody id="fmtBody">
              <tr v-if="app.fmtTableMessage">
                <td colspan="5" class="empty-hint" :style="app.fmtTableError ? 'color:var(--danger)' : ''">
                  {{ app.fmtTableMessage }}
                </td>
              </tr>
              <tr
                v-for="(format, index) in app.filteredFormats"
                :key="format.format_id"
                :class="{ selected: app.selectedIdx === index }"
                @click="app.selectFormat(index)"
              >
                <td><strong>{{ format.resolution }}</strong></td>
                <td>
                  <span v-if="isHdrRange(format.dynamic_range)" class="range-hdr">
                    {{ format.dynamic_range }}
                  </span>
                  <template v-else>{{ format.dynamic_range || 'SDR' }}</template>
                </td>
                <td>{{ formatFpsTable(format.fps) }}</td>
                <td>
                  <span class="badge-codec" :class="getCodecClass(format.codec)">{{ format.codec }}</span>
                </td>
                <td class="right">{{ formatSize(format) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </div>
    </main>
  </div>
</template>

<style src="~/assets/css/main.css" />

<style scoped>
.main-app {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.grain {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.35;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 180px 180px;
  mix-blend-mode: overlay;
}
</style>
