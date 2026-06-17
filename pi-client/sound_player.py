"""
星火智造云打印 — 打印完成提示音服务
使用 pygame 或系统命令 (aplay/paplay) 播放提示音
"""

import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 提示音文件 (可选自定义 wav/mp3) ──
_SCRIPT_DIR = Path(__file__).resolve().parent
_CUSTOM_SOUND = _SCRIPT_DIR / "print_done.wav"


class SoundPlayer:
    """打印完成提示音播放器"""

    def __init__(self, enabled: bool = True, volume: float = 0.7):
        self._enabled = enabled
        self._volume = max(0.0, min(1.0, volume))
        self._backend = self._detect_backend()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def _detect_backend(self) -> str:
        """检测可用的音频后端"""
        # 优先使用 pygame (跨平台, 支持音量控制)
        try:
            import pygame.mixer
            pygame.mixer.init(frequency=22050, size=-16, channels=1)
            logger.info("🔊 音频后端: pygame")
            return "pygame"
        except Exception:
            pass

        # 树莓派 ALSA
        if subprocess.run(["which", "aplay"], capture_output=True).returncode == 0:
            logger.info("🔊 音频后端: aplay (ALSA)")
            return "aplay"

        # PulseAudio
        if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0:
            logger.info("🔊 音频后端: paplay (PulseAudio)")
            return "paplay"

        # 其他
        if subprocess.run(["which", "mpg123"], capture_output=True).returncode == 0:
            logger.info("🔊 音频后端: mpg123")
            return "mpg123"

        logger.warning("⚠️ 未检测到可用音频后端, 提示音将被禁用")
        return "none"

    def play_success(self):
        """播放打印成功提示音 (三声短促滴)"""
        if not self._enabled:
            return

        try:
            if self._backend == "pygame":
                self._play_pygame_beeps([(880, 0.12), (0, 0.06), (1100, 0.12), (0, 0.06), (1320, 0.2)])
            elif self._backend == "aplay":
                self._play_system_beeps("aplay", 3, 0.12)
            elif self._backend == "paplay":
                self._play_system_beeps("paplay", 3, 0.12)
            elif self._backend == "mpg123":
                self._play_custom_or_beep()
            else:
                self._play_console_bell()
        except Exception as e:
            logger.debug(f"播放提示音异常: {e}")

    def play_error(self):
        """播放打印失败提示音 (两声低沉)"""
        if not self._enabled:
            return

        try:
            if self._backend == "pygame":
                self._play_pygame_beeps([(400, 0.2), (0, 0.1), (300, 0.35)])
            else:
                self._play_console_bell()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # 内部实现
    # ═══════════════════════════════════════════════════════════════

    def _play_pygame_beeps(self, notes: list):
        """用 pygame 合成蜂鸣音

        Args:
            notes: [(频率Hz, 时长s), ...]  频率 0 = 静音
        """
        import pygame.sndarray
        import numpy

        sample_rate = 22050
        total_samples = int(sum(dur for _, dur in notes) * sample_rate)
        waveform = numpy.zeros(total_samples, dtype=numpy.int16)

        offset = 0
        for freq, duration in notes:
            n_samples = int(duration * sample_rate)
            if freq > 0 and n_samples > 0:
                t = numpy.linspace(0, duration, n_samples, endpoint=False)
                # 正弦波 + 指数衰减包络
                envelope = numpy.exp(-3.0 * t / duration) if duration > 0 else 1.0
                tone = (numpy.sin(2 * numpy.pi * freq * t) * envelope * 16000 * self._volume).astype(numpy.int16)
                waveform[offset:offset + n_samples] = tone
            offset += n_samples

        sound = pygame.sndarray.make_sound(waveform)
        sound.play()
        time.sleep(sum(dur for _, dur in notes) + 0.1)

    def _play_system_beeps(self, cmd: str, count: int, duration: float):
        """使用系统命令播放控制台蜂鸣 (兜底)"""
        for _ in range(count):
            # 使用 /dev/console 蜂鸣 (需要 beep 模块加载)
            try:
                with open("/dev/console", "wb") as f:
                    f.write(b"\x07")
            except Exception:
                pass
            time.sleep(duration)

    def _play_custom_or_beep(self):
        """播放自定义音频文件或回退到蜂鸣"""
        if _CUSTOM_SOUND.exists():
            try:
                subprocess.run(
                    ["mpg123", "-q", str(_CUSTOM_SOUND)],
                    timeout=10,
                )
                return
            except Exception:
                pass
        self._play_console_bell()

    def _play_console_bell(self):
        """播放控制台蜂鸣 (ASCII BEL)"""
        print("\a", end="", flush=True)


# ── 单例 ──
_player: SoundPlayer | None = None


def get_sound_player(enabled: bool = True, volume: float = 0.7) -> SoundPlayer:
    """获取 SoundPlayer 单例"""
    global _player
    if _player is None:
        _player = SoundPlayer(enabled=enabled, volume=volume)
    return _player


def play_print_done():
    """便捷函数: 播放打印完成提示音"""
    if _player:
        _player.play_success()


def play_print_error():
    """便捷函数: 播放打印失败提示音"""
    if _player:
        _player.play_error()
