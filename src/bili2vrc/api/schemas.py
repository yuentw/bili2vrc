from pydantic import BaseModel, Field


class FetchFormatsRequest(BaseModel):
    url: str = ""
    cookie_content: str | None = None


class ProcessRequest(BaseModel):
    url: str = ""
    format_id: str = ""
    key_phrase: str = ""
    ttl: int | None = None
    compat_mode: bool = False
    playback_speed: float = 1.0
    bitrate_kbps: int | None = None
    encode_quality: str | None = None
    encode_mode: str | None = None
    encode_crf: int | None = Field(default=None, ge=0, le=63)
    scale_bitrate_with_speed: bool | None = None
    output_codec: str | None = None
    cookie_content: str | None = None


class ProcessCancelRequest(BaseModel):
    job_id: str | None = None


class ErrorResponse(BaseModel):
    error: str


class CancelResponse(BaseModel):
    ok: bool
    error: str | None = None
