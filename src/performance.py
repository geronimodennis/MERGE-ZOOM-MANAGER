import logging
from time import perf_counter, sleep


LOGGER_NAME = "merge_zoom_manager"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class FpsCounter:
    def __init__(self, report_interval: float = 2.0):
        self.report_interval = report_interval
        self.frames = 0
        self.last_report = perf_counter()
        self.average_fps = 0.0

    def tick(self) -> float:
        self.frames += 1
        now = perf_counter()
        elapsed = now - self.last_report
        if elapsed >= self.report_interval:
            self.average_fps = self.frames / elapsed
            self.frames = 0
            self.last_report = now
        return self.average_fps


class FrameRateLimiter:
    def __init__(self, target_fps: int):
        self.target_fps = max(1, int(target_fps))
        self.frame_interval = 1.0 / self.target_fps

    def sleep_remaining(self, started_at: float) -> None:
        remaining = self.frame_interval - (perf_counter() - started_at)
        if remaining > 0:
            sleep(remaining)
