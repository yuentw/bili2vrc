from fastapi import APIRouter

from bili2vrc.encoding import hwaccel

router = APIRouter()


@router.get("/hwaccel-status")
def hwaccel_status_route():
    probe = hwaccel.get_probe_result()
    encoder = probe.encoder
    return {
        "encoder": encoder.name,
        "label": encoder.label,
        "fallback": encoder.fallback,
        "available": probe.available,
        "smoke_failures": probe.smoke_failures,
        "decode_hwaccel": hwaccel.decode_hwaccel_args(encoder),
        "gpus": probe.gpus,
        "note": probe.note,
    }
