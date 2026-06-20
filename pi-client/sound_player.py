"""
星火智造云打印 — 打印完成语音播报服务
支持 TTS (espeak-ng / gTTS / edge-tts) + pygame 蜂鸣回退
"""

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent

# ── 默认 TTS 短语 ──
TTS_SUCCESS = "打印完成"
TTS_FAILURE = "打印失败，请检查打印机"

# ── 播报后端优先级 ──
_TTS_BACKENDS = ["espeak-ng", "espeak", "edge-tts", "gtts", "say"]


class SoundPlayer:
    """打印完成语音播报播放器

    多后端 TTS:
      - espeak-ng / espeak:  离线, 轻量, 推荐树莓派 (需 apt install espeak-ng)
      - edge-tts:           在线, 高质量中文 (pip install edge-tts)
      - gtts:               在线, Google TTS (pip install gtts)
      - say:                macOS 原生
      - pygame 蜂鸣:        纯 Python 合成, 无网络无依赖回退
    """

    def __init__(
        self,
        enabled: bool = True,
        volume: float = 0.7,
        tts_success: str = "",
        tts_failure: str = "",
    ):
        self._enabled = enabled
        self._volume = max(0.0, min(1.0, volume))
        self._tts_success = tts_success or TTS_SUCCESS
        self._tts_failure = tts_failure or TTS_FAILURE

        self._tts_backend = self._detect_tts()
        self._fallback = self._detect_audio()
        self._log_diagnosis()

    # ═══════════════════════════════════════════════════════════════
    # 启动诊断 — 暴露问题, 不要静默
    # ═══════════════════════════════════════════════════════════════

    def _log_diagnosis(self):
        """启动时打印一次完整诊断, 便于排查 systemd 下无声问题"""
        if not self._enabled:
            logger.info("🔇 TTS 已禁用 (ENABLE_SOUND=false), 跳过诊断")
            return

        logger.info(f"🔊 TTS 诊断:")
        logger.info(f"   TTS 后端:    {self._tts_backend}")
        logger.info(f"   音频后端:    {self._fallback}")
        logger.info(f"   音量:        {self._volume}")
        logger.info(f"   成功文本:    {self._tts_success}")
        logger.info(f"   失败文本:    {self._tts_failure}")

        if self._tts_backend == "none":
            logger.warning(
                "⚠️ 没有找到任何 TTS 后端! 安装命令:\n"
                "     sudo apt install -y espeak-ng                  # 离线, 推荐\n"
                "     pip3 install edge-tts --break-system-packages  # 在线高质量"
            )
        if self._fallback == "none":
            logger.warning(
                "⚠️ 没有找到音频播放后端! 安装命令:\n"
                "     sudo apt install -y alsa-utils                 # 提供 aplay\n"
                "     pip3 install pygame --break-system-packages    # 跨平台备选"
            )

        # systemd 环境检查: User=root + 缺 XDG_RUNTIME_DIR 是无声第一原因
        import os
        if os.getuid() == 0 and not os.environ.get("XDG_RUNTIME_DIR"):
            logger.warning(
                "⚠️ 检测到 root 用户且无 XDG_RUNTIME_DIR, "
                "PulseAudio 可能无法访问。建议:\n"
                "     1) 修改 service: User=pi (而非 root)\n"
                "     2) 或在 service 加: Environment=XDG_RUNTIME_DIR=/run/user/1000\n"
                "     3) 或用 ALSA 直出 (espeak 默认走 ALSA, 应该可用)"
            )

    # ═══════════════════════════════════════════════════════════════
    # 公开 API
    # ═══════════════════════════════════════════════════════════════

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def play_success(self):
        """播报打印成功"""
        if not self._enabled:
            logger.debug("TTS 已禁用 (ENABLE_SOUND=false)")
            return
        try:
            self._speak(self._tts_success)
            logger.info(f"🔊 已播报: {self._tts_success}")
        except Exception as e:
            logger.warning(f"⚠️ TTS 成功播报失败: {type(e).__name__}: {e} → 回退蜂鸣")
            try:
                self._play_beep_success()
            except Exception as e2:
                logger.error(f"❌ 蜂鸣回退也失败: {type(e2).__name__}: {e2}")

    def play_error(self):
        """播报打印失败"""
        if not self._enabled:
            logger.debug("TTS 已禁用 (ENABLE_SOUND=false)")
            return
        try:
            self._speak(self._tts_failure)
            logger.info(f"🔊 已播报: {self._tts_failure}")
        except Exception as e:
            logger.warning(f"⚠️ TTS 失败播报失败: {type(e).__name__}: {e} → 回退蜂鸣")
            try:
                self._play_beep_error()
            except Exception as e2:
                logger.error(f"❌ 蜂鸣回退也失败: {type(e2).__name__}: {e2}")

    def speak(self, text: str):
        """播报任意文本 (调试用)"""
        if not self._enabled:
            return
        self._speak(text)

    # ═══════════════════════════════════════════════════════════════
    # TTS 后端检测与调用
    # ═══════════════════════════════════════════════════════════════

    def _detect_tts(self) -> str:
        """按优先级检测可用 TTS 后端"""
        for backend in _TTS_BACKENDS:
            if backend in ("espeak-ng", "espeak"):
                bin_name = backend  # espeak-ng 的二进制也叫 espeak-ng
                if shutil.which(bin_name) or shutil.which("espeak"):
                    logger.info(f"🗣️  TTS 后端: {backend}")
                    return backend
            elif backend == "edge-tts":
                try:
                    import edge_tts  # noqa: F401
                    logger.info(f"🗣️  TTS 后端: edge-tts")
                    return backend
                except ImportError:
                    pass
            elif backend == "gtts":
                try:
                    from gtts import gTTS  # noqa: F401
                    logger.info(f"🗣️  TTS 后端: gtts")
                    return backend
                except ImportError:
                    pass
            elif backend == "say":
                if shutil.which("say"):
                    logger.info(f"🗣️  TTS 后端: say (macOS)")
                    return backend

        logger.warning("⚠️ 无 TTS 后端可用, 将使用蜂鸣")
        return "none"

    def _detect_audio(self) -> str:
        """检测音频播放后端 (用于 gTTS 等需要播放 mp3 的场景)"""
        try:
            import pygame.mixer
            pygame.mixer.init(frequency=24000, size=-16, channels=1)
            return "pygame"
        except Exception:
            pass
        for cmd in ("aplay", "paplay", "mpg123", "ffplay", "play"):
            if shutil.which(cmd):
                return cmd
        return "none"

    def _speak(self, text: str):
        """使用 TTS 后端播报文本"""
        backend = self._tts_backend

        try:
            if backend in ("espeak-ng", "espeak"):
                self._speak_espeak(text)
            elif backend == "edge-tts":
                self._speak_edge_tts(text)
            elif backend == "gtts":
                self._speak_gtts(text)
            elif backend == "say":
                self._speak_say(text)
            else:
                raise RuntimeError("无 TTS 后端")
        except Exception:
            raise

    # ── espeak-ng / espeak ─────────────────────

    def _speak_espeak(self, text: str):
        """espeak-ng TTS (离线, 最佳树莓派选择)"""
        # 优先 espeak-ng, 其次 espeak
        binary = shutil.which("espeak-ng") or shutil.which("espeak") or "espeak"
        speed = int(100 + (1 - self._volume) * 80)  # 音量映射到语速辅助

        # 捕获 stderr, 方便排查 ALSA / PulseAudio 错误
        result = subprocess.run(
            [
                binary,
                "-v", "zh",           # 中文普通话
                "-s", str(speed),     # 语速 (80-450, 默认 175)
                "-a", str(int(self._volume * 200)),  # 音量 (0-200)
                text,
            ],
            timeout=15,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip() or "espeak 静默失败"
            raise RuntimeError(f"espeak 退出码 {result.returncode}: {err}")
        # 即使返回 0, stderr 里也可能有 ALSA underrun 警告, 帮助诊断
        if result.stderr and result.stderr.strip():
            logger.debug(f"espeak stderr: {result.stderr.strip()}")

    # ── edge-tts (在线, 高质量) ────────────────

    def _speak_edge_tts(self, text: str):
        """Microsoft Edge TTS (免费在线, 中文自然)"""
        import asyncio

        async def _run():
            import edge_tts
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name

            try:
                communicate = edge_tts.Communicate(
                    text,
                    voice="zh-CN-XiaoxiaoNeural",  # 中文女声
                    rate="+0%",
                    volume="+0%",
                )
                await communicate.save(tmp_path)
                self._play_audio_file(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _run())
                    future.result(timeout=15)
            else:
                asyncio.run(_run())
        except RuntimeError:
            asyncio.run(_run())

    # ── gTTS (在线, Google) ───────────────────

    def _speak_gtts(self, text: str):
        """Google TTS (在线, 需 pip install gtts)"""
        from gtts import gTTS

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name

        try:
            tts = gTTS(text=text, lang="zh-cn", slow=False)
            tts.save(tmp_path)
            self._play_audio_file(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── macOS say ──────────────────────────────

    def _speak_say(self, text: str):
        """macOS 原生 TTS"""
        subprocess.run(
            ["say", "-v", "Tingting", text],
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # ═══════════════════════════════════════════════════════════════
    # 音频文件播放 (gTTS / edge-tts 生成 mp3 后播放)
    # ═══════════════════════════════════════════════════════════════

    def _play_audio_file(self, filepath: str):
        """用检测到的音频后端播放 mp3/wav 文件"""
        backend = self._fallback

        try:
            if backend == "pygame":
                import pygame.mixer
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            elif backend == "aplay":
                subprocess.run(["aplay", "-q", filepath], timeout=30)
            elif backend == "paplay":
                subprocess.run(["paplay", filepath], timeout=30)
            elif backend == "mpg123":
                subprocess.run(["mpg123", "-q", filepath], timeout=30)
            elif backend == "ffplay":
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filepath],
                    timeout=30,
                )
            elif backend == "play":
                subprocess.run(["play", "-q", filepath], timeout=30)
            else:
                raise RuntimeError("无音频播放后端")
        except Exception as e:
            logger.debug(f"音频播放失败: {e}")
            raise

    # ═══════════════════════════════════════════════════════════════
    # 蜂鸣回退 (无 TTS 无音频时)
    # ═══════════════════════════════════════════════════════════════

    def _play_beep_success(self):
        """三声上扬蜂鸣"""
        self._beep_sequence([(880, 0.12), (0, 0.06), (1100, 0.12), (0, 0.06), (1320, 0.2)])

    def _play_beep_error(self):
        """两声低沉蜂鸣"""
        self._beep_sequence([(400, 0.2), (0, 0.1), (300, 0.35)])

    def _beep_sequence(self, notes: list):
        """pygame 合成蜂鸣"""
        try:
            import pygame.sndarray
            import numpy

            sample_rate = 24000
            total_samples = int(sum(dur for _, dur in notes) * sample_rate)
            waveform = numpy.zeros(total_samples, dtype=numpy.int16)

            offset = 0
            for freq, duration in notes:
                n_samples = int(duration * sample_rate)
                if freq > 0 and n_samples > 0:
                    t = numpy.linspace(0, duration, n_samples, endpoint=False)
                    envelope = numpy.exp(-3.0 * t / max(duration, 0.001))
                    tone = (numpy.sin(2 * numpy.pi * freq * t) * envelope * 12000 * self._volume).astype(numpy.int16)
                    waveform[offset:offset + n_samples] = tone
                offset += n_samples

            sound = pygame.sndarray.make_sound(waveform)
            sound.play()
            time.sleep(sum(dur for _, dur in notes) + 0.1)
        except ImportError:
            print("\a", end="", flush=True)


# ── 单例 ──
_player: SoundPlayer | None = None


def get_sound_player(
    enabled: bool = True,
    volume: float = 0.7,
    tts_success: str = "",
    tts_failure: str = "",
) -> SoundPlayer:
    """获取 SoundPlayer 单例"""
    global _player
    if _player is None:
        _player = SoundPlayer(
            enabled=enabled,
            volume=volume,
            tts_success=tts_success,
            tts_failure=tts_failure,
        )
    return _player
