<script setup lang="ts">
import {
  codecFamilyLabel,
  formatFpsTable,
  formatSize,
  getRetroCodecClass,
} from '~/composables/useFormatUtils'

useHead({
  title: 'bili2vrchat - B站→VRChat 上傳工具',
})

const app = reactive(useBili2Vrc())
const cookieFileInput = ref<HTMLInputElement | null>(null)
const previewVideo = ref<HTMLVideoElement | null>(null)
const hideCookieWarning = ref(false)

onMounted(() => {
  app.loadHwaccelStatus()
  app.updateCookieWarningForUrl(String(app.urlInput ?? ''))

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
</script>

<template>
  <div class="retro-app">
    <div class="page-wrap">
      <div class="xp-window">
        <div class="titlebar">
          <div class="titlebar-left">
            <span class="titlebar-icon">🎬</span>
            bili2vrchat — B站→Cloudflare R2→VRChat 上傳工具
          </div>
          <div class="win-controls">
            <div class="wc-btn">0</div>
            <div class="wc-btn">1</div>
            <div class="wc-btn close">r</div>
          </div>
        </div>

        <div class="menubar">
          <div class="menu-item">檔案(F)</div>
          <div class="menu-item">檢視(V)</div>
          <div class="menu-item">工具(T)</div>
          <div class="menu-item">說明(H)</div>
        </div>

        <div class="toolbar">
          <button
            class="xp-btn-primary xp-btn"
            :disabled="app.fetchLoading"
            @click="app.fetchFormats(true)"
          >
            {{ app.fetchLoading ? '載入中...' : '🔍 獲取格式(G)' }}
          </button>
          <div class="tb-sep" />
          <button
            class="xp-btn-primary xp-btn"
            :disabled="!app.selectedFormat || app.processLoading"
            @click="app.startProcess(true)"
          >
            ▶ 下載並上傳(U)
          </button>
          <button
            v-if="app.showCancelBtn"
            class="xp-btn xp-btn"
            :disabled="app.cancelBtnDisabled"
            @click="app.cancelProcess(true)"
          >
            ✕ 取消
          </button>
          <div class="tb-sep" />
          <span id="selInfo" style="font-size:11px;color:#404040;flex:1">{{ app.selInfoText }}</span>
        </div>

        <div class="addrbar">
          <span class="addr-label">網址(D):</span>
          <input
            class="addr-input"
            type="text"
            v-model="app.urlInput"
            placeholder="bilibili.com/video/... 或 youtube.com/watch?v=..."
            autocomplete="off"
            spellcheck="false"
            @input="app.onUrlInput(app.urlInput)"
            @keydown="onUrlKeydown"
          >
          <button class="addr-go" @click="app.fetchFormats(true)">移至</button>
        </div>

        <div
          v-if="app.showCookieWarning && !hideCookieWarning"
          class="ie-infobar"
          id="cookieWarning"
          style="display: flex"
        >
          <span>{{ app.cookieWarningText }}</span>
          <button class="ie-infobar-btn" @click="hideCookieWarning = true">關閉(X)</button>
        </div>

        <div class="marquee-strip">
          <marquee behavior="scroll" direction="left" scrollamount="3">
            ★★★ B站→VRChat 影片中轉工具 ★ 請在上方輸入網址並點擊「獲取格式」★ 建議選擇 H.264 格式以獲最佳 VRChat 相容性 ★ 上傳後連結可直接貼入 VRChat 影片播放器使用 ★★★
          </marquee>
        </div>

        <div class="xp-body">
          <div class="xp-panel" style="margin-bottom:8px">
            <div class="xp-panel-title">🍪 Cookie（儲存於瀏覽器）</div>
            <div class="cookie-panel-body">
              <input
                ref="cookieFileInput"
                class="file-input-hidden"
                type="file"
                accept=".txt,text/plain"
                @change="onCookieFileChange"
              >
              <button
                class="xp-btn cookie-file-picker"
                type="button"
                @click="cookieFileInput?.click()"
              >
                選擇 cookies.txt 檔案
              </button>
              <div id="cookiePlatforms">
                <div
                  v-for="platform in app.COOKIE_PLATFORMS"
                  :key="platform"
                  :class="app.cookieStatus[platform] ? 'ok' : 'warn'"
                >
                  {{ app.platformLabel(platform) }}:
                  {{ app.cookieStatus[platform] ? '已設定' : '未設定' }}
                  <button
                    v-if="app.cookieStatus[platform]"
                    class="xp-btn"
                    type="button"
                    style="font-size:10px;padding:1px 6px"
                    @click="app.clearCookiePlatform(platform, true)"
                  >
                    清除
                  </button>
                </div>
              </div>
            </div>
            <div v-if="app.cookieUploadMsg" id="cookieUploadMsg" style="padding:0 8px 6px">
              {{ app.cookieUploadMsg }}
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

          <div class="xp-panel">
            <div class="xp-panel-title">
              <span>📋 格式列表
                <span id="fmtCount" style="font-weight:normal;font-size:10px">{{ app.retroFmtCountLabel }}</span>
              </span>
              <div class="codec-filter-group retro-codec-filter">
                <span class="codec-filter-label">編碼:</span>
                <div class="codec-btn-group" role="group" aria-label="編碼篩選">
                  <button
                    v-for="family in app.codecFamilies"
                    :key="family"
                    type="button"
                    class="xp-btn codec-btn"
                    :class="{ active: app.codecFamily === family }"
                    :disabled="app.codecFamilies.length <= 1"
                    @click="app.setCodecFamily(family)"
                  >
                    {{ codecFamilyLabel(family) }}
                  </button>
                </div>
              </div>
            </div>
            <div style="overflow-x:auto;border-top:1px solid #aca899">
              <table class="xp-listview" id="fmtTable">
                <thead>
                  <tr>
                    <th style="width:120px">解析度</th>
                    <th style="width:60px">範圍</th>
                    <th style="width:90px">FPS</th>
                    <th style="width:110px">編碼</th>
                    <th class="right" style="width:90px">大小</th>
                  </tr>
                </thead>
                <tbody id="fmtBody">
                  <tr v-if="app.fmtTableMessage">
                    <td colspan="5" class="empty-hint" :style="app.fmtTableError ? 'color:red' : ''">
                      {{ app.fmtTableMessage }}
                    </td>
                  </tr>
                  <tr
                    v-for="(format, index) in app.filteredFormats"
                    :key="format.format_id"
                    :class="{ selected: app.selectedIdx === index }"
                    @click="app.selectFormat(index)"
                  >
                    <td>{{ format.resolution }}</td>
                    <td>{{ format.dynamic_range || 'SDR' }}</td>
                    <td>{{ formatFpsTable(format.fps) }}</td>
                    <td>
                      <span class="codec-tag" :class="getRetroCodecClass(format.codec)">
                        {{ format.codec }}
                      </span>
                    </td>
                    <td class="right">{{ formatSize(format) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <hr class="xp-hr">

          <div class="xp-panel">
            <div class="xp-panel-title">⚙ 上傳設定</div>
            <div style="padding:8px">
              <div class="field-row">
                <div class="field-col">
                  <label class="xp-label" for="keyPhrase">自訂路徑名稱 (留空則自動隨機產生):</label>
                  <input class="xp-input" type="text" id="keyPhrase" v-model="app.keyPhrase" placeholder="例如: myvideo" autocomplete="off">
                </div>
                <div class="field-col">
                  <label class="xp-label" for="ttlSelect">檔案保存時間:</label>
                  <select class="xp-select" id="ttlSelect" v-model="app.ttl">
                    <option :value="3600">1 小時後自動刪除</option>
                    <option :value="86400">1 天後自動刪除</option>
                    <option :value="604800">7 天後自動刪除</option>
                    <option :value="2592000">30 天後自動刪除</option>
                    <option :value="0">永久保存</option>
                  </select>
                </div>
              </div>
              <div class="field-row">
                <div class="field-col">
                  <label class="xp-label" for="playbackSpeed">播放速度（上傳前永久變更）:</label>
                  <select
                    class="xp-select"
                    id="playbackSpeed"
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
                  <div
                    class="xp-hint"
                    :class="{ 'xp-hint-warn': app.playbackSpeedForcesReencode }"
                  >
                    {{ app.playbackSpeedReencodeWarning }}
                  </div>
                </div>
              </div>
              <div class="field-row">
                <div class="field-col field-col-full">
                  <label class="xp-label">輸出模式:</label>
                  <div class="codec-btn-group output-mode-group" role="group" aria-label="輸出模式">
                    <button
                      v-for="option in app.outputModeOptions"
                      :key="option.value"
                      type="button"
                      class="xp-btn codec-btn"
                      :class="{ active: app.outputMode === option.value }"
                      :disabled="option.value === 'original' && app.originalModeDisabled"
                      @click="app.setOutputMode(option.value)"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                  <div class="xp-hint">{{ app.outputModeHint }}</div>
                </div>
              </div>
              <div v-if="app.selectedIsHdr" class="field-row">
                <div class="field-col field-col-full">
                  <label class="xp-check-label">
                    <input type="checkbox" v-model="app.tonemapHdr">
                    <span>HDR → SDR（tonemap）</span>
                  </label>
                  <div class="xp-hint">{{ app.tonemapHdrHint }}</div>
                </div>
              </div>

              <details v-if="app.showAdvancedEncoding" class="xp-advanced-options">
                <summary class="xp-advanced-summary">進階編碼選項</summary>
                <div class="field-row">
                  <div class="field-col">
                    <label class="xp-label" for="encodeMode">編碼模式（重新編碼時）:</label>
                    <select class="xp-select" id="encodeMode" v-model="app.encodeMode">
                      <option
                        v-for="option in app.encodeModeOptions"
                        :key="option.value"
                        :value="option.value"
                      >
                        {{ option.label }}
                      </option>
                    </select>
                  </div>
                  <div v-if="app.selectedIsHdr" class="field-col">
                    <label class="xp-label" for="tonemapAlgorithm">Mapping（HDR→SDR）:</label>
                    <select
                      class="xp-select"
                      id="tonemapAlgorithm"
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
                    <div class="xp-hint">{{ app.tonemapAlgorithmHint }}</div>
                  </div>
                  <div class="field-col">
                    <label class="xp-label crf-label-row" for="encodeCrf">
                      <span>{{ app.encodeCrfLabel }}</span>
                      <span class="crf-value">{{ app.encodeCrf }}</span>
                    </label>
                    <input
                      class="crf-slider"
                      type="range"
                      id="encodeCrf"
                      v-model.number="app.encodeCrf"
                      :min="app.encodeCrfConfig.min"
                      :max="app.encodeCrfConfig.max"
                      step="1"
                    >
                    <div class="crf-range-labels">
                      <span>{{ app.crfRangeLabels.low }}</span>
                      <span>{{ app.crfRangeLabels.high }}</span>
                    </div>
                    <div class="xp-hint">{{ app.encodeCrfConfig.hint }}</div>
                  </div>
                </div>
                <div class="field-row">
                  <div class="field-col">
                    <label class="xp-label" for="bitrateKbps">{{ app.bitrateFieldLabel }}:</label>
                    <select class="xp-select" id="bitrateKbps" v-model.number="app.bitrateKbps">
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
                    <div class="xp-hint">
                      {{ app.bitrateFieldHint }}
                      <template v-if="Number(app.playbackSpeed) !== 1 && app.scaleBitrateWithSpeed">
                        。倍速實際{{ app.encodeMode === 'cbr' ? '目標' : '上限' }}
                        {{ app.bitrateCeilingKbps }} kbps（選取值 × {{ app.playbackSpeed }}x）
                      </template>
                    </div>
                  </div>
                </div>
                <div id="hwEncoderLabel">{{ app.hwEncoderLabel }}</div>
              </details>
            </div>
          </div>

          <div v-if="app.showProgressBar" class="xp-progress" id="progressBar" style="display: block">
            <div class="xp-progress-fill" id="progressFill" />
          </div>

          <div v-if="app.showStatusBox" class="xp-status-text" id="statusBox" style="display: block">
            <span id="statusMsg">{{ app.statusMsg }}</span>
          </div>

          <div v-if="app.showResultBox" class="xp-result" id="resultBox" style="display: block">
            <div class="xp-result-title">✅ 上傳完成！VRChat 直連網址如下：</div>
            <div class="xp-result-row">
              <input class="xp-result-url" type="text" id="resultUrl" readonly :value="app.resultUrl">
              <button class="xp-btn" id="copyBtn" @click="copyRetroUrl">{{ app.copyBtnText }}</button>
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
            <div class="xp-hint">
              💡 在 VRChat 影片播放器中貼上此連結即可播放 &nbsp;|&nbsp; 連結有效期依上方設定而定
            </div>
          </div>
        </div>

        <div class="statusbar">
          <span class="sb-panel" id="statusPanel">{{ app.statusBarMsg }}</span>
          <span class="sb-panel sb-fixed" style="width:140px" id="cookiePanel">{{ app.cookiePanelText }}</span>
          <span class="sb-panel sb-fixed" style="width:70px">Port: 5000</span>
        </div>
      </div>

      <div class="xp-window" style="font-size:11px">
        <div class="titlebar">
          <div class="titlebar-left"><span>🖥</span> 主題切換</div>
        </div>
        <div style="padding:4px 8px;background:#ece9d8;display:flex;gap:6px;align-items:center">
          <NuxtLink to="/" class="xp-btn theme-btn">現代版</NuxtLink>
          <button class="xp-btn" disabled style="font-weight:bold">Windows XP 版（目前）</button>
        </div>
      </div>

      <div class="page-footer">
        此頁面最佳解析度：800×600 | 建議使用 Microsoft Internet Explorer 6.0 SP2 以上版本瀏覽<br>
        bili2vrchat v1.0 &copy; 2003–2026 | B站→Cloudflare R2→VRChat
      </div>
    </div>
  </div>
</template>

<style src="~/assets/css/retro.css" />

<style scoped>
.retro-app :deep(.theme-btn) {
  text-decoration: none;
  color: #000;
  display: inline-block;
}

.retro-app :deep(.retro-codec-filter) {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-weight: normal;
  font-size: 10px;
}

.retro-app :deep(.retro-codec-filter .codec-btn-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.retro-app :deep(.retro-codec-filter .codec-btn) {
  font-size: 10px;
  padding: 2px 8px;
  min-width: auto;
  min-height: 22px;
}

.retro-app :deep(.retro-codec-filter .codec-btn.active) {
  background: linear-gradient(to bottom, #4a8ed8 0%, #2b5db7 100%);
  border-color: #fff #1a3a80 #1a3a80 #fff;
  outline-color: #1a3a80;
  color: white;
  font-weight: bold;
}

.retro-app :deep(.field-col-full) {
  flex: 1 1 100%;
  width: 100%;
}

.retro-app :deep(.output-mode-group) {
  display: flex;
  gap: 2px;
}

.retro-app :deep(.output-mode-group .codec-btn) {
  flex: 1;
  min-width: 0;
  font-size: 10px;
  padding: 2px 6px;
  min-height: 22px;
}
</style>
