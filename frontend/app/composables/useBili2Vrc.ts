import type { VideoFormat, VideoMeta } from './useFormatUtils'
import { normalizeCodecFamily, sortCodecFamilies } from './useFormatUtils'

type ProcessEvent = {
  type: string
  job_id?: string
  step?: string
  message?: string
  url?: string
}

export function useBili2Vrc() {
  const cookieStore = useCookieStore()

  const urlInput = ref('')
  const keyPhrase = ref('')
  const ttl = ref(604800)
  const playbackSpeed = ref(1)
  const bitrateKbps = ref(3000)
  const sourceBitrateKbps = ref<number | null>(null)
  const encodeQuality = ref('balanced')
  const encodeMode = ref('vbr')
  const compatMode = ref(false)
  const vbrBitratePresets = [1500, 2000, 3000, 4000, 5000, 8000]
  const cbrBitratePresets = [2000, 4000, 5000, 6000, 8000, 10000]
  const encodeModeOptions = [
    { value: 'vbr', label: 'VBR（品質 + 碼率上限）' },
    { value: 'cbr', label: 'CBR（固定碼率）' },
  ]
  const encodeQualityOptions = [
    { value: 'high', label: '高畫質（檔案較大）' },
    { value: 'balanced', label: '標準' },
    { value: 'medium', label: '較小檔案' },
    { value: 'small', label: '最小檔案' },
  ]
  const bitrateFieldLabel = computed(() =>
    encodeMode.value === 'cbr' ? '目標碼率（重新編碼時）' : '碼率上限（重新編碼時）',
  )
  const usingSourceBitrate = computed(() => {
    const source = sourceBitrateKbps.value
    return source != null && Number(bitrateKbps.value) === source
  })
  // CBR 選固定預設時不 × 倍速；原片 CBR / VBR 仍會 × 倍速
  const scaleBitrateWithSpeed = computed(
    () => encodeMode.value !== 'cbr' || usingSourceBitrate.value,
  )
  const bitrateFieldHint = computed(() => {
    if (encodeMode.value === 'cbr') {
      if (usingSourceBitrate.value) {
        return '原片 CBR；倍速時會自動 × 倍速調整目標碼率'
      }
      return '固定碼率；自訂預設不隨倍速調整碼率'
    }
    return '以品質為主，並強制遵守碼率上限'
  })
  const bitrateSelectOptions = computed(() => {
    const source = sourceBitrateKbps.value
    const presets = (encodeMode.value === 'cbr' ? cbrBitratePresets : vbrBitratePresets)
      .filter((kbps) => kbps !== source)
    return { source, presets }
  })

  const bitrateCeilingKbps = computed(() => {
    const base = Number(bitrateKbps.value) || 3000
    const speed = Number(playbackSpeed.value) || 1
    if (!scaleBitrateWithSpeed.value || Math.abs(speed - 1) < 1e-6) {
      return Math.round(base)
    }
    return Math.max(500, Math.min(50000, Math.round(base * speed)))
  })

  watch(encodeMode, (mode) => {
    const source = sourceBitrateKbps.value
    const current = Number(bitrateKbps.value)
    if (source != null && current === source) return
    const presets = mode === 'cbr' ? cbrBitratePresets : vbrBitratePresets
    if (!presets.includes(current)) {
      bitrateKbps.value = presets.includes(4000) ? 4000 : (presets[0] ?? 3000)
    }
  })

  const allFormats = ref<VideoFormat[]>([])
  const filteredFormats = ref<VideoFormat[]>([])
  const selectedFormat = ref<VideoFormat | null>(null)
  const selectedIdx = ref(-1)
  const codecFamilies = ref<string[]>([])
  const codecFamily = ref('h264')

  const videoMeta = ref<VideoMeta | null>(null)
  const showVideoMeta = ref(false)
  const fmtTableMessage = ref('請先輸入網址並點擊「獲取格式」')
  const fmtTableError = ref(false)
  const fmtCountShown = ref(0)
  const fmtCountTotal = ref(0)

  const fetchLoading = ref(false)
  const processLoading = ref(false)
  const activeJobId = ref<string | null>(null)
  const statusDotClass = ref('spin')
  const statusMsg = ref('等待中...')
  const statusBarMsg = ref('就緒')
  const showStatusBox = ref(false)
  const showProgressBar = ref(false)
  const showResultBox = ref(false)
  const resultUrl = ref('')
  const copyBtnText = ref('複製')
  const previewSpeed = ref(1)
  const hwEncoderLabel = ref('編碼器：偵測中...')

  const selInfoText = ref('尚未選擇格式')
  const showCancelBtn = ref(false)
  const cancelBtnDisabled = ref(false)

  const fmtCountLabel = computed(() => {
    if (!fmtCountShown.value && !fmtCountTotal.value) return ''
    if (fmtCountShown.value === fmtCountTotal.value) {
      return `${fmtCountShown.value} 個`
    }
    return `${fmtCountShown.value} / ${fmtCountTotal.value} 個`
  })

  const retroFmtCountLabel = computed(() => {
    if (!fmtCountShown.value && !fmtCountTotal.value) return ''
    if (fmtCountShown.value === fmtCountTotal.value) {
      return `共 ${fmtCountShown.value} 個`
    }
    return `${fmtCountShown.value} / ${fmtCountTotal.value} 個`
  })

  const cookiePanelText = computed(() => {
    const status = cookieStore.cookieStatus.value
    return status.bilibili || status.youtube ? 'Cookie: 已設定 ✓' : 'Cookie: 未設定 ✗'
  })

  function onUrlInput(value: string | undefined) {
    const normalized = value ?? ''
    urlInput.value = normalized
    cookieStore.updateCookieWarningForUrl(normalized)
  }

  async function loadHwaccelStatus() {
    try {
      const response = await fetch('/api/hwaccel-status')
      const data = await response.json()
      const note = typeof data.note === 'string' && data.note ? ` — ${data.note}` : ''
      if (data.fallback) {
        hwEncoderLabel.value = `編碼器：${data.label}${note}`
      } else {
        const decode = Array.isArray(data.decode_hwaccel)
          ? data.decode_hwaccel.filter((part: string) => part !== '-hwaccel').join('/')
          : ''
        const decodeHint = decode ? ` · 解碼 ${decode}` : ''
        hwEncoderLabel.value = `編碼器：${data.label}${decodeHint}${note}`
      }
    } catch {
      hwEncoderLabel.value = '編碼器：未知'
    }
  }

  function resetFormatTable(message: string, isError = false) {
    allFormats.value = []
    filteredFormats.value = []
    selectedFormat.value = null
    selectedIdx.value = -1
    codecFamilies.value = []
    codecFamily.value = 'h264'
    sourceBitrateKbps.value = null
    bitrateKbps.value = 3000
    fmtTableMessage.value = message
    fmtTableError.value = isError
    fmtCountShown.value = 0
    fmtCountTotal.value = 0
    selInfoText.value = '尚未選擇格式'
  }

  function applySourceBitrate(format: VideoFormat) {
    const raw = Number(format.bitrate_kbps)
    if (!Number.isFinite(raw) || raw < 1) {
      sourceBitrateKbps.value = null
      return
    }
    const kbps = Math.max(500, Math.min(50000, Math.round(raw)))
    sourceBitrateKbps.value = kbps
    bitrateKbps.value = kbps
  }

  function applyVideoMeta(data: VideoMeta & { formats?: VideoFormat[] }) {
    const title = (data.title || '').trim()
    if (!title && !data.thumbnail) {
      showVideoMeta.value = false
      videoMeta.value = null
      return
    }
    videoMeta.value = {
      title: title || '（無標題）',
      thumbnail: data.thumbnail,
      uploader: data.uploader,
      duration_formatted: data.duration_formatted,
    }
    showVideoMeta.value = true
  }

  function populateCodecFilter(formats: VideoFormat[]) {
    const families = sortCodecFamilies(
      [...new Set(formats.map((format) => normalizeCodecFamily(format.codec)))],
    )
    codecFamilies.value = families
    codecFamily.value = families.includes('h264') ? 'h264' : families[0] || 'other'
  }

  function applyCodecFilter() {
    const filtered = allFormats.value.filter(
      (format) => normalizeCodecFamily(format.codec) === codecFamily.value,
    )
    filteredFormats.value = filtered
    fmtCountShown.value = filtered.length
    fmtCountTotal.value = allFormats.value.length

    if (!filtered.length) {
      fmtTableMessage.value = '此編碼無可用格式'
      fmtTableError.value = false
      selectedFormat.value = null
      selectedIdx.value = -1
      selInfoText.value = '尚未選擇格式'
      return
    }

    fmtTableMessage.value = ''
    selectFormat(0)
  }

  function selectFormat(index: number) {
    const format = filteredFormats.value[index]
    if (!format) return
    selectedIdx.value = index
    selectedFormat.value = format
    applySourceBitrate(format)
    const fps = format.fps ? `${format.fps.toFixed(3)} fps` : ''
    const bitrate = sourceBitrateKbps.value ? `  ${sourceBitrateKbps.value} kbps` : ''
    selInfoText.value = `已選擇: ${format.resolution}  ${format.codec}  ${fps}${bitrate}`
    statusBarMsg.value = `已選取格式：${format.resolution} ${format.codec} ${fps}${bitrate}`
  }

  async function fetchFormats(retro = false) {
    const url = urlInput.value.trim()
    if (!url) return

    fetchLoading.value = true
    resetFormatTable(
      retro ? '正在連線至 B 站伺服器，請稍候...' : '取得格式中，請稍候...',
    )
    showVideoMeta.value = false
    videoMeta.value = null
  if (retro) statusBarMsg.value = '正在取得格式列表...'

    try {
      const response = await fetch('/api/fetch-formats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cookieStore.buildRequestBody(url)),
      })
      const data = await response.json()

      if (data.error) {
        resetFormatTable(
          retro ? `錯誤：${data.error}` : data.error,
          true,
        )
        if (retro) statusBarMsg.value = '錯誤：取得格式失敗'
        return
      }

      applyVideoMeta(data)
      const formats = data.formats || []
      if (!formats.length) {
        resetFormatTable('未找到可用格式')
        return
      }

      allFormats.value = formats
      populateCodecFilter(formats)
      applyCodecFilter()
      cookieStore.updateCookieWarningForUrl(url)
      if (retro) statusBarMsg.value = '就緒'
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      resetFormatTable(
        retro ? `網路錯誤：${message}` : `網路錯誤：${message}`,
        true,
      )
      if (retro) statusBarMsg.value = '網路連線錯誤'
    } finally {
      fetchLoading.value = false
    }
  }

  function setStatus(dotClass: string, message: string) {
    statusDotClass.value = dotClass
    statusMsg.value = message
  }

  function handleProcessEvent(event: ProcessEvent, retro = false) {
    if (event.type === 'started') {
      activeJobId.value = event.job_id || null
      showCancelBtn.value = true
      cancelBtnDisabled.value = false
    } else if (event.type === 'status') {
      const dotClass = event.step === 'done' ? 'done' : 'spin'
      setStatus(dotClass, event.message || '')
      if (retro) statusBarMsg.value = event.message || ''
    } else if (event.type === 'error') {
      activeJobId.value = null
      showCancelBtn.value = false
      showProgressBar.value = false
      setStatus('error', retro ? `❌ 錯誤：${event.message}` : `❌ ${event.message}`)
      if (retro) statusBarMsg.value = `錯誤：${event.message}`
    } else if (event.type === 'result') {
      activeJobId.value = null
      showCancelBtn.value = false
      showProgressBar.value = false
      if (retro) {
        setStatus(`✅ ${event.url}`, event.url || '')
        statusBarMsg.value = '上傳完成'
      } else {
        setStatus('done', '完成')
      }
      showResult(event.url || '', retro)
    }
  }

  async function parseSseResponse(response: Response, retro = false) {
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6)) as ProcessEvent
          handleProcessEvent(event, retro)
        } catch {
          /* skip malformed SSE line */
        }
      }
    }
  }

  async function startProcess(retro = false) {
    if (!selectedFormat.value) return

    const url = urlInput.value.trim()
    showResultBox.value = false
    showStatusBox.value = true
    showProgressBar.value = retro
    setStatus('spin', retro ? '初始化...' : '準備下載...')
    if (retro) statusBarMsg.value = '正在下載影片，請勿關閉此視窗...'

    processLoading.value = true
    fetchLoading.value = true
    activeJobId.value = null
    showCancelBtn.value = false
    cancelBtnDisabled.value = false

    try {
      const response = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          cookieStore.buildRequestBody(url, {
            format_id: selectedFormat.value.format_id,
            key_phrase: keyPhrase.value.trim(),
            ttl: Number(ttl.value),
            compat_mode: Boolean(compatMode.value),
            playback_speed: Number(playbackSpeed.value) || 1,
            bitrate_kbps: Number(bitrateKbps.value) || 3000,
            encode_quality: encodeQuality.value || 'balanced',
            encode_mode: encodeMode.value || 'vbr',
            scale_bitrate_with_speed: scaleBitrateWithSpeed.value,
          }),
        ),
      })
      await parseSseResponse(response, retro)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setStatus('error', retro ? `錯誤：${message}` : `連線中斷：${message}`)
      showProgressBar.value = false
      if (retro) statusBarMsg.value = '發生錯誤，請重試'
    } finally {
      activeJobId.value = null
      showCancelBtn.value = false
      processLoading.value = false
      fetchLoading.value = false
    }
  }

  async function cancelProcess(retro = false) {
    if (!activeJobId.value) return
    cancelBtnDisabled.value = true
    setStatus('spin', '正在取消...')
    if (retro) statusBarMsg.value = '正在取消...'
    try {
      await fetch('/api/process/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: activeJobId.value }),
      })
    } catch {
      /* ignore cancel errors */
    }
  }

  function showResult(url: string, retro = false) {
    resultUrl.value = url
    showResultBox.value = true
    copyBtnText.value = retro ? retroCopyLabel(false) : modernCopyLabel(false)
    previewSpeed.value = 1
  }

  function retroCopyLabel(copied: boolean) {
    return copied ? '已複製 ✓' : '複製(C)'
  }

  function modernCopyLabel(copied: boolean) {
    return copied ? '✓ 已複製' : '複製'
  }

  async function copyUrl(retro = false) {
    const setCopied = (ok: boolean) => {
      if (retro) {
        copyBtnText.value = ok ? '已複製 ✓' : '請手動複製'
      } else {
        copyBtnText.value = ok ? '✓ 已複製' : '請手動複製↑'
      }
      const resetLabel = retro ? '複製(C)' : '複製'
      setTimeout(() => {
        copyBtnText.value = resetLabel
      }, retro ? 2500 : 2000)
    }

    const fallback = () => {
      const textarea = document.createElement('textarea')
      textarea.value = resultUrl.value
      textarea.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      let ok = false
      try {
        ok = document.execCommand('copy')
      } catch {
        /* execCommand may fail on some browsers */
      }
      document.body.removeChild(textarea)
      setCopied(ok)
    }

    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(resultUrl.value)
        setCopied(true)
      } catch {
        fallback()
      }
    } else {
      fallback()
    }
  }

  async function uploadCookie(file: File | undefined, retro = false) {
    cookieStore.cookieUploadMsg.value = ''
    if (!file) {
      alert('請先選擇 cookies.txt 檔案')
      return
    }
    try {
      const content = await file.text()
      const result = cookieStore.saveCookieFromFile(content, file.name)
      if (!result.ok) {
        alert(result.error)
        return
      }
      cookieStore.cookieUploadMsg.value = result.message
      cookieStore.updateCookieWarningForUrl(urlInput.value)
      if (retro) statusBarMsg.value = result.message
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      alert(`讀取失敗：${message}`)
    }
  }

  function clearCookiePlatform(platform: 'bilibili' | 'youtube', retro = false) {
    cookieStore.clearCookie(platform)
    cookieStore.updateCookieWarningForUrl(urlInput.value)
    if (retro) statusBarMsg.value = 'Cookie 已清除'
  }

  function onPreviewSpeedChange(speed: number, videoEl: HTMLVideoElement | null) {
    previewSpeed.value = speed
    if (videoEl) {
      videoEl.preservesPitch = true
      videoEl.playbackRate = speed
    }
  }

  function onResultVideoLoaded(videoEl: HTMLVideoElement | null) {
    if (videoEl) {
      videoEl.preservesPitch = true
      videoEl.playbackRate = previewSpeed.value
    }
  }

  return {
    ...cookieStore,
    urlInput,
    keyPhrase,
    ttl,
    playbackSpeed,
    bitrateKbps,
    sourceBitrateKbps,
    vbrBitratePresets,
    cbrBitratePresets,
    bitrateSelectOptions,
    bitrateCeilingKbps,
    bitrateFieldLabel,
    bitrateFieldHint,
    usingSourceBitrate,
    scaleBitrateWithSpeed,
    encodeMode,
    encodeModeOptions,
    encodeQuality,
    encodeQualityOptions,
    compatMode,
    allFormats,
    filteredFormats,
    selectedFormat,
    selectedIdx,
    codecFamilies,
    codecFamily,
    videoMeta,
    showVideoMeta,
    fmtTableMessage,
    fmtTableError,
    fmtCountShown,
    fmtCountTotal,
    fmtCountLabel,
    retroFmtCountLabel,
    fetchLoading,
    processLoading,
    activeJobId,
    statusDotClass,
    statusMsg,
    statusBarMsg,
    showStatusBox,
    showProgressBar,
    showResultBox,
    resultUrl,
    copyBtnText,
    previewSpeed,
    hwEncoderLabel,
    selInfoText,
    showCancelBtn,
    cancelBtnDisabled,
    cookiePanelText,
    onUrlInput,
    loadHwaccelStatus,
    applyCodecFilter,
    selectFormat,
    fetchFormats,
    startProcess,
    cancelProcess,
    copyUrl,
    uploadCookie,
    clearCookiePlatform,
    onPreviewSpeedChange,
    onResultVideoLoaded,
  }
}
