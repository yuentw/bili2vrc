export interface VideoFormat {
  format_id: string
  resolution: string
  codec: string
  fps?: number
  dynamic_range?: string
  size: string
  size_approx?: boolean
}

export interface VideoMeta {
  title?: string
  thumbnail?: string
  uploader?: string
  duration_formatted?: string
}

const CODEC_ORDER = ['h264', 'h265', 'av1', 'vp9', 'other']

const CODEC_FAMILY_LABELS: Record<string, string> = {
  h264: 'H.264',
  h265: 'H.265 / HEVC',
  av1: 'AV1',
  vp9: 'VP9',
  other: '其他',
}

export function esc(str: unknown): string {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function normalizeCodecFamily(codec: string | undefined): string {
  if (!codec) return 'other'
  const codecLower = codec.toLowerCase()
  if (codecLower.includes('h.264') || codecLower.includes('264') || codecLower.includes('avc')) return 'h264'
  if (codecLower.includes('h.265') || codecLower.includes('265') || codecLower.includes('hevc')) return 'h265'
  if (codecLower.includes('av1')) return 'av1'
  if (codecLower.includes('vp9')) return 'vp9'
  return 'other'
}

export function codecFamilyLabel(family: string): string {
  return CODEC_FAMILY_LABELS[family] || family
}

export function getCodecClass(codec: string | undefined): string {
  if (!codec) return 'codec-other'
  const codecLower = codec.toLowerCase()
  if (codecLower.includes('h.264') || codecLower.includes('264')) return 'codec-h264'
  if (codecLower.includes('h.265') || codecLower.includes('265') || codecLower.includes('hevc')) return 'codec-h265'
  if (codecLower.includes('av1')) return 'codec-av1'
  if (codecLower.includes('vp9')) return 'codec-vp9'
  return 'codec-other'
}

export function getRetroCodecClass(codec: string | undefined): string {
  if (!codec) return ''
  const codecLower = codec.toLowerCase()
  if (codecLower.includes('264') || codecLower.includes('avc')) return ''
  if (codecLower.includes('265') || codecLower.includes('hevc')) return 'c265'
  if (codecLower.includes('av1')) return 'cav1'
  if (codecLower.includes('vp9')) return 'cvp9'
  return ''
}

export function sortCodecFamilies(families: string[]): string[] {
  return [...families].sort((a, b) => {
    const indexA = CODEC_ORDER.indexOf(a)
    const indexB = CODEC_ORDER.indexOf(b)
    return (indexA === -1 ? 99 : indexA) - (indexB === -1 ? 99 : indexB)
  })
}

export function isHdrRange(range: string | undefined): boolean {
  return range === 'HDR' || range === 'HDR10' || range === 'HLG'
}

export function formatSize(format: VideoFormat): string {
  return format.size_approx ? `~${format.size}` : format.size
}

export function formatFpsTable(fps: number | undefined): string {
  return fps ? `${fps.toFixed(3)}fps` : '-'
}

export function formatFpsLabel(fps: number | undefined): string {
  return fps ? `${fps.toFixed(3)} fps` : ''
}
