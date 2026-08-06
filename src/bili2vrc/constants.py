PLAYBACK_SPEED_MIN = 0.5
PLAYBACK_SPEED_MAX = 2.0


def clamp_playback_speed(speed: float) -> float:
    return max(PLAYBACK_SPEED_MIN, min(PLAYBACK_SPEED_MAX, speed))
