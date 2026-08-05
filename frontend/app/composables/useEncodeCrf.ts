export type OutputCodecKey = 'h264' | 'h265' | 'av1'

export const ENCODE_CRF_CONFIG: Record<
  OutputCodecKey,
  { min: number; max: number; default: number; hint: string }
> = {
  h264: {
    min: 0,
    max: 51,
    default: 19,
    hint:
      'H.264：CRF / NVENC CQ 0–51，18–23 常用。硬體 VideoToolbox 會換算為 q:v（愈高畫質愈好）。',
  },
  h265: {
    min: 0,
    max: 51,
    default: 22,
    hint: 'H.265 / HEVC：CRF 尺度與 H.264 相近，同畫質下常用值通常高 1–2。',
  },
  av1: {
    min: 0,
    max: 63,
    default: 30,
    hint: 'AV1 (SVT-AV1)：CRF 0–63，尺度不同，28–35 常用；同視覺品質下數值通常高於 H.264。',
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
