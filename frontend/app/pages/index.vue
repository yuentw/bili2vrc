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
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' }],
})

const app = reactive(useBili2Vrc())
const cookieFileInput = ref<HTMLInputElement | null>(null)
const previewVideo = ref<HTMLVideoElement | null>(null)

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

async function pasteAndFetch() {
  if (app.fetchLoading) return
  try {
    const text = (await navigator.clipboard.readText()).trim()
    if (!text) {
      alert('剪貼簿是空的')
      return
    }
    app.onUrlInput(text)
    await app.fetchFormats()
  } catch {
    alert('無法讀取剪貼簿，請允許貼上權限，或手動貼上網址')
  }
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
    <header>
      <h1>🎬 bili2vrchat</h1>
      <span class="badge">B站 / YouTube → R2 → VRChat</span>
      <!-- <NuxtLink to="/retro" class="badge theme-link" disabled>Windows XP 版</NuxtLink> -->
    </header>

    <main>
      <div class="section">
        <div class="section-title">影片網址</div>
        <div class="section-body">
          <div class="url-row">
            <input
              type="text"
              v-model="app.urlInput"
              placeholder="B站或 YouTube 網址，如 bilibili.com/video/... 或 youtube.com/watch?v=..."
              autocomplete="off"
              spellcheck="false"
              @input="app.onUrlInput(app.urlInput)"
              @keydown="onUrlKeydown"
            >
            <button
              class="btn btn-ghost"
              type="button"
              :disabled="app.fetchLoading"
              @click="pasteAndFetch"
            >
              貼上
            </button>
            <button
              class="btn btn-primary"
              :disabled="app.fetchLoading"
              @click="app.fetchFormats()"
            >
              {{ app.fetchLoading ? '載入中...' : '獲取格式' }}
            </button>
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
              class="btn btn-ghost cookie-file-picker"
              type="button"
              @click="cookieFileInput?.click()"
            >
              選擇 cookies.txt 檔案
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
                  {{ app.cookieStatus[platform] ? '已設定' : '未設定' }}
                </span>
                <button
                  v-if="app.cookieStatus[platform]"
                  class="btn btn-ghost btn-sm"
                  type="button"
                  @click="app.clearCookiePlatform(platform)"
                >
                  清除
                </button>
              </div>
            </div>
          </div>
          <div v-if="app.cookieUploadMsg" id="cookieUploadMsg">{{ app.cookieUploadMsg }}</div>
        </div>
      </div>

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

      <div class="section">
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
                @click="app.codecFamily = family; app.applyCodecFilter()"
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

      <div class="section">
        <div class="section-title">上傳選項</div>
        <div class="section-body">
          <div class="options-grid">
            <div class="field">
              <label>自訂路徑名稱（留空自動隨機）</label>
              <input type="text" v-model="app.keyPhrase" placeholder="例如: myvideo" autocomplete="off">
            </div>
            <div class="field">
              <label>保存時間</label>
              <select v-model="app.ttl">
                <option :value="3600">1 小時後自動刪除</option>
                <option :value="86400">1 天後自動刪除</option>
                <option :value="604800">7 天後自動刪除</option>
                <option :value="2592000">30 天後自動刪除</option>
                <option :value="0">永久保存</option>
              </select>
            </div>
            <div class="field">
              <label>播放速度（上傳前永久變更）</label>
              <select
                :value="app.playbackSpeed"
                @change="app.playbackSpeed = Number(($event.target as HTMLSelectElement).value)"
              >
                <option :value="0.5">0.5x（慢速）</option>
                <option :value="0.75">0.75x</option>
                <option :value="1">1.0x（原速）</option>
                <option :value="1.25">1.25x</option>
                <option :value="1.5">1.5x</option>
                <option :value="1.75">1.75x</option>
                <option :value="2">2.0x（快速）</option>
              </select>
            </div>
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
            <div class="field">
              <label>編碼品質（重新編碼時）</label>
              <select v-model="app.encodeQuality">
                <option
                  v-for="option in app.encodeQualityOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
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
              <label class="compat-check">
                <input type="checkbox" v-model="app.compatMode">
                <span>VRChat 相容模式 — 重新編碼為 H.264（修復固定時間點撕裂，較慢）</span>
              </label>
              <div id="hwEncoderLabel">{{ app.hwEncoderLabel }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-body">
          <div class="action-bar">
            <button
              class="btn btn-primary"
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
            <div id="selInfo">
              <template v-if="app.selectedFormat">
                已選擇 <span>{{ app.selectedFormat.resolution }}</span>
                {{ app.selectedFormat.codec }}
                {{ formatFpsLabel(app.selectedFormat.fps) }}
              </template>
              <template v-else>尚未選擇格式</template>
            </div>
          </div>
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
    </main>
  </div>
</template>

<style src="~/assets/css/main.css" />

<style scoped>
.main-app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.theme-link {
  text-decoration: none;
  cursor: pointer;
  background: var(--surface2);
  color: var(--text);
}

.theme-link:hover {
  background: var(--border);
}
</style>
