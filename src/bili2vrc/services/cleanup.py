import logging
import threading
import time

from bili2vrc import config
from bili2vrc.storage import r2

logger = logging.getLogger("bili2vrchat")


def r2_credentials_configured() -> bool:
    return config.storage_configured()


def run_r2_cleanup() -> None:
    if not r2_credentials_configured():
        return
    scanned, deleted = r2.purge_expired_objects()
    if deleted:
        logger.info("r2 cleanup: scanned=%s deleted=%s", scanned, deleted)
    else:
        logger.debug("r2 cleanup: scanned=%s deleted=0", scanned)


def start_r2_cleanup_thread() -> None:
    if not config.R2_CLEANUP_ENABLED:
        logger.info("r2 cleanup disabled")
        return
    if not r2_credentials_configured():
        logger.warning("r2 cleanup skipped: storage credentials not configured")
        return

    def cleanup_loop() -> None:
        while True:
            try:
                run_r2_cleanup()
            except Exception:
                logger.exception("r2 cleanup failed")
            time.sleep(config.R2_CLEANUP_INTERVAL)

    thread = threading.Thread(target=cleanup_loop, name="r2-cleanup", daemon=True)
    thread.start()
    logger.info("r2 cleanup thread started (interval=%ss)", config.R2_CLEANUP_INTERVAL)
