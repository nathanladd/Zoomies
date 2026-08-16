"""Projector-side sound effects for the instructor app.

Owned by GameControlPanel (not ProjectionWindow) so sound keeps working from
the instructor's speakers even before a projection window exists or while
it's hidden — the panel already dispatches every WS event, so it's the
natural place to trigger playback alongside the proj.on_* calls.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from instructor import app_settings

TENSION_TRACK_COUNT = 5


def _sounds_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "media" / "sounds"
    return Path(__file__).resolve().parent.parent.parent / "media" / "sounds"


class SoundManager:
    """Plays lobby/answer one-shot SFX and a randomized background tension
    track for the current question.

    Everything goes through QMediaPlayer, including the one-shot SFX —
    QSoundEffect (the usual choice for low-latency clips) can't load
    compressed mp3/ogg on this Qt6/Windows build (its decoder only accepts
    raw WAV there), while QMediaPlayer decodes them fine.

    Answers can arrive in a burst as multiple students submit around the
    same moment, so the correct/wrong/join chimes are played on transient,
    self-cleaning QMediaPlayer instances (``_play_transient``) rather than a
    single shared player — reusing one player would cut off the previous
    sound every time a new answer came in instead of letting them overlap.
    """

    def __init__(self) -> None:
        settings = app_settings.load()
        self._muted: bool = settings.get("sound_muted", False)
        self._volume: float = settings.get("sound_volume", 0.7)

        sounds = _sounds_dir()
        self._new_player_sound = sounds / "new_player.ogg"
        self._correct_sound = sounds / "correct.mp3"
        self._wrong_sound = sounds / "wrong-buzzer.mp3"
        # Keeps a strong reference to each in-flight transient player/output
        # pair so Python doesn't garbage-collect it mid-playback.
        self._transient: list[tuple[QMediaPlayer, QAudioOutput]] = []

        self._tension_tracks = [
            sounds / f"time_{i}.mp3" for i in range(1, TENSION_TRACK_COUNT + 1)
        ]
        self._tension_output = QAudioOutput()
        self._tension_player = QMediaPlayer()
        self._tension_player.setAudioOutput(self._tension_output)

        self._apply_volume()

    def _apply_volume(self) -> None:
        vol = 0.0 if self._muted else self._volume
        for _player, output in self._transient:
            output.setVolume(vol)
        self._tension_output.setVolume(vol)

    def _play_transient(self, path: Path) -> None:
        vol = 0.0 if self._muted else self._volume
        output = QAudioOutput()
        output.setVolume(vol)
        player = QMediaPlayer()
        player.setAudioOutput(output)
        player.setSource(QUrl.fromLocalFile(str(path)))

        pair = (player, output)
        self._transient.append(pair)

        def _on_status_changed(status: QMediaPlayer.MediaStatus) -> None:
            if status in (
                QMediaPlayer.MediaStatus.EndOfMedia,
                QMediaPlayer.MediaStatus.InvalidMedia,
            ):
                if pair in self._transient:
                    self._transient.remove(pair)
                player.deleteLater()
                output.deleteLater()

        player.mediaStatusChanged.connect(_on_status_changed)
        player.play()

    # ── Instructor controls ─────────────────────────────────────────────

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def muted(self) -> bool:
        return self._muted

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        self._apply_volume()
        app_settings.save(sound_volume=self._volume)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        self._apply_volume()
        app_settings.save(sound_muted=muted)

    # ── Triggers ─────────────────────────────────────────────────────────

    def play_player_joined(self) -> None:
        self._play_transient(self._new_player_sound)

    def play_answer(self, is_correct: bool) -> None:
        """Play a correct/wrong chime for a single player's submitted
        answer, as it arrives — separate from the reveal, so a burst of
        answers produces a burst of overlapping dings/buzzes."""
        self._play_transient(self._correct_sound if is_correct else self._wrong_sound)

    def start_question_tension(self) -> None:
        """Start a randomly chosen tension track for the question that just
        started. Loops in case a track ever runs shorter than the question
        (none currently do — the tracks run several minutes)."""
        track = random.choice(self._tension_tracks)
        self._tension_player.setSource(QUrl.fromLocalFile(str(track)))
        self._tension_player.setLoops(QMediaPlayer.Loops.Infinite)
        self._tension_player.play()

    def stop_question_tension(self) -> None:
        self._tension_player.stop()
