import subprocess
import threading


class ProcessController:
    """追蹤進行中的下載/轉檔任務，支援取消並終止子進程"""

    def __init__(self):
        self._lock = threading.Lock()
        self._job_id: str | None = None
        self._cancel_event: threading.Event | None = None
        self._procs: list[subprocess.Popen] = []

    def begin(self, job_id: str) -> threading.Event:
        with self._lock:
            self._stop_procs()
            self._job_id = job_id
            self._cancel_event = threading.Event()
            self._procs = []
            return self._cancel_event

    def register_proc(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.append(proc)

    def cancel(self, job_id: str | None = None) -> bool:
        with self._lock:
            if job_id and self._job_id != job_id:
                return False
            if not self._job_id:
                return False
            if self._cancel_event:
                self._cancel_event.set()
            self._stop_procs()
            return True

    def clear(self, job_id: str) -> None:
        with self._lock:
            if self._job_id == job_id:
                self._job_id = None
                self._cancel_event = None
                self._procs = []

    def _stop_procs(self) -> None:
        for proc in self._procs:
            self._kill_proc(proc)
        self._procs = []

    def _kill_proc(self, proc: subprocess.Popen) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=3)
            except Exception:
                pass


process_controller = ProcessController()
