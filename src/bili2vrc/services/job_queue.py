"""FIFO queue for download/transcode/upload jobs (one active at a time)."""
from __future__ import annotations

import logging
import queue
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from bili2vrc import config
from bili2vrc.services.pipeline import run_process
from bili2vrc.services.process_controller import process_controller

logger = logging.getLogger("bili2vrchat.job_queue")

_HEARTBEAT_INTERVAL = 15.0


@dataclass
class QueuedJob:
    job_id: str
    event_queue: queue.Queue
    cancel_event: threading.Event = field(default_factory=threading.Event)
    url: str = ""
    format_id: str = ""
    key_phrase: str = ""
    ttl: int = 0
    compat_mode: bool = False
    playback_speed: float = 1.0
    bitrate_kbps: int = 3000
    encode_quality: str = "balanced"
    encode_mode: str = "vbr"
    scale_bitrate_with_speed: bool = True
    output_codec: str = "h264"
    encode_crf: int | None = None
    tonemap_hdr: bool = False
    tonemap_algorithm: str = "mobius"
    cookie_path: str | None = None


class JobQueue:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._waiting: deque[QueuedJob] = deque()
        self._jobs_by_id: dict[str, QueuedJob] = {}
        self._active_job_id: str | None = None
        self._worker_started = False
        self._heartbeat_stop = threading.Event()

    def queue_status(self) -> dict:
        with self._lock:
            queued_count = len(self._waiting)
            active = self._active_job_id is not None
            total_count = queued_count + (1 if active else 0)
            max_queue = config.MAX_PROCESS_QUEUE
            return {
                "active": active,
                "queued_count": queued_count,
                "total_count": total_count,
                "max_queue": max_queue,
                "available_slots": max(0, max_queue - total_count),
            }

    def position(self, job_id: str) -> int | None:
        with self._lock:
            for index, job in enumerate(self._waiting, start=1):
                if job.job_id == job_id:
                    return index
            return None

    def enqueue(
        self,
        *,
        event_queue: queue.Queue,
        url: str,
        format_id: str,
        key_phrase: str,
        ttl: int,
        compat_mode: bool,
        playback_speed: float,
        bitrate_kbps: int,
        encode_quality: str,
        encode_mode: str,
        scale_bitrate_with_speed: bool,
        output_codec: str,
        encode_crf: int | None,
        tonemap_hdr: bool,
        tonemap_algorithm: str,
        cookie_path: str | None,
    ) -> str | None:
        with self._lock:
            total = len(self._waiting) + (1 if self._active_job_id else 0)
            if total >= config.MAX_PROCESS_QUEUE:
                return None
            job_id = secrets.token_hex(8)
            job = QueuedJob(
                job_id=job_id,
                event_queue=event_queue,
                url=url,
                format_id=format_id,
                key_phrase=key_phrase,
                ttl=ttl,
                compat_mode=compat_mode,
                playback_speed=playback_speed,
                bitrate_kbps=bitrate_kbps,
                encode_quality=encode_quality,
                encode_mode=encode_mode,
                scale_bitrate_with_speed=scale_bitrate_with_speed,
                output_codec=output_codec,
                encode_crf=encode_crf,
                tonemap_hdr=tonemap_hdr,
                tonemap_algorithm=tonemap_algorithm,
                cookie_path=cookie_path,
            )
            self._jobs_by_id[job_id] = job
            self._waiting.append(job)
            self._cond.notify()
            is_waiting = self._active_job_id is not None or len(self._waiting) > 1

        if is_waiting:
            self._emit_queued_status(job)
        logger.info("job enqueued: job_id=%s position=%s", job_id, self.position(job_id))
        return job_id

    def cancel(self, job_id: str | None) -> bool:
        if not job_id:
            return False
        with self._lock:
            if self._active_job_id == job_id:
                return process_controller.cancel(job_id)
            job = self._jobs_by_id.get(job_id)
            if not job:
                return False
            try:
                self._waiting.remove(job)
            except ValueError:
                return False
            job.cancel_event.set()
            del self._jobs_by_id[job_id]

        job.event_queue.put({"type": "error", "message": "已取消"})
        job.event_queue.put(None)
        logger.info("queued job cancelled: job_id=%s", job_id)
        return True

    def queue_fields_for(self, job_id: str) -> dict:
        status = self.queue_status()
        position = self.position(job_id)
        return {
            "queue_count": status["total_count"],
            "queue_max": status["max_queue"],
            "queue_position": position,
        }

    def start_worker(self) -> None:
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True
        threading.Thread(target=self._worker_loop, name="job-queue-worker", daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, name="job-queue-heartbeat", daemon=True).start()
        logger.info("job queue worker started (max=%s)", config.MAX_PROCESS_QUEUE)

    def _worker_loop(self) -> None:
        while True:
            with self._cond:
                while not self._waiting:
                    self._cond.wait()
                job = self._waiting.popleft()

            if job.cancel_event.is_set():
                with self._lock:
                    self._jobs_by_id.pop(job.job_id, None)
                continue

            with self._lock:
                self._active_job_id = job.job_id

            self._emit_queued_status(job, starting=True)
            cancel_event = process_controller.begin(job.job_id)
            worker = threading.Thread(
                target=run_process,
                args=(
                    job.url,
                    job.format_id,
                    job.key_phrase,
                    job.ttl,
                    job.compat_mode,
                    job.playback_speed,
                    job.bitrate_kbps,
                    job.encode_quality,
                    job.encode_mode,
                    job.scale_bitrate_with_speed,
                    job.output_codec,
                    job.encode_crf,
                    job.tonemap_hdr,
                    job.tonemap_algorithm,
                    job.cookie_path,
                    job.job_id,
                    cancel_event,
                    job.event_queue,
                ),
                daemon=True,
            )
            worker.start()
            worker.join()

            with self._lock:
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
                self._jobs_by_id.pop(job.job_id, None)

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(_HEARTBEAT_INTERVAL):
            with self._lock:
                waiting = list(self._waiting)
            for job in waiting:
                if not job.cancel_event.is_set():
                    self._emit_queued_status(job)

    def _emit_queued_status(self, job: QueuedJob, *, starting: bool = False) -> None:
        status = self.queue_status()
        position = self.position(job.job_id)
        total = status["total_count"]
        max_queue = status["max_queue"]
        if starting:
            message = f"開始處理（{total}/{max_queue}）…"
        elif position:
            message = f"排隊中（{total}/{max_queue}，第 {position} 位）…"
        else:
            message = f"排隊中（{total}/{max_queue}）…"
        job.event_queue.put({
            "type": "status",
            "step": "queued",
            "message": message,
            "queue_count": total,
            "queue_max": max_queue,
            "queue_position": position,
        })


job_queue = JobQueue()


def start_job_queue_worker() -> None:
    job_queue.start_worker()
