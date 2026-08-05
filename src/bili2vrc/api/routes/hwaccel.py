from fastapi import APIRouter, Query

from bili2vrc import config
from bili2vrc.encoding import hwaccel

router = APIRouter()


@router.get("/hwaccel-status")
def hwaccel_status_route(codec: str | None = Query(default=None)):
    output_codec = config.normalize_output_codec(codec)
    probe = hwaccel.get_probe_result(output_codec)
    encoder = probe.encoder
    return {
        "output_codec": output_codec,
        "output_codec_label": config.OUTPUT_CODEC_LABELS.get(output_codec, output_codec.upper()),
        "encoder": encoder.name,
        "label": encoder.label,
        "fallback": encoder.fallback,
        "available": probe.available,
        "smoke_failures": probe.smoke_failures,
        "decode_hwaccel": hwaccel.decode_hwaccel_args(encoder),
        "hw_accel_disabled": config.DISABLE_HW_ACCEL,
        "gpus": probe.gpus,
        "note": probe.note,
    }
