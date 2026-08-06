export type OutputCodecKey = 'h264' | 'h265' | 'av1'

/** Shown under slider; CRF/CQ: lower = better, 0 ≈ lossless. */
export const CRF_QUALITY_NOTE =
  '愈低畫質愈好，0 為無損；愈高檔案愈小、畫質愈差。'

export const CRF_RANGE_LABELS = {
  low: '高畫質（0≈無損）',
  high: '低畫質／小檔',
} as const

export const ENCODE_CRF_CONFIG: Record<
  OutputCodecKey,
  { min: number; max: number; default: number; hint: string }
> = {
  h264: {
    min: 0,
    max: 51,
    default: 19,
    hint:
      `${CRF_QUALITY_NOTE} H.264／NVENC CQ：0–51，18–23 常用。Apple VideoToolbox 會換算為 q:v（該參數愈高畫質愈好，與 CRF 方向相反）。`,
  },
  h265: {
    min: 0,
    max: 51,
    default: 22,
    hint: `${CRF_QUALITY_NOTE} H.265／HEVC：尺度與 H.264 相近，同畫質下常用值通常比 H.264 高 1–2。`,
  },
  av1: {
    min: 0,
    max: 63,
    default: 30,
    hint: `${CRF_QUALITY_NOTE} AV1 (SVT-AV1／NVENC)：0–63，尺度不同，28–35 常用；同視覺品質下數值通常高於 H.264。`,
  },
}

export function normalizeOutputCodecKey(codec: string): OutputCodecKey {
  if (codec === 'av1') return 'av1'
  if (codec === 'h265' || codec === 'hevc') return 'h265'
  return 'h264'
}

export function clampEncodeCrf(codec: string, value: number): number {
  const key = normalizeOutputCodecKey(codec)
  const cfg = ENCODE_CRF_CONFIG[key]
  return Math.max(cfg.min, Math.min(cfg.max, Math.round(value)))
}

export function defaultEncodeCrfByCodec(): Record<OutputCodecKey, number> {
  return {
    h264: ENCODE_CRF_CONFIG.h264.default,
    h265: ENCODE_CRF_CONFIG.h265.default,
    av1: ENCODE_CRF_CONFIG.av1.default,
  }
}
