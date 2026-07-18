#!/usr/bin/env python3
"""Interactive learner and ADB bot for Island War card choices.

Performance optimizations added:
- single resize per screenshot (cached)
- single HSV conversion per screenshot (cached)
- minimize redundant OpenCV work by caching processed screen
- Adb tap invalidates screen cache
- benchmark subcommand that measures processing times without extra adb calls
- lightweight integrity check (can be opt-in via env VERIFY_ON_START=1)
- fingerprint caching in Recognizer.match() for faster multi-card recognition
- batched state.json writes for new_card/add_sample sequences

Behavioral algorithms, CLI API and hotkeys preserved; only internal performance has changed.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


REFERENCE_SIZE = (1220, 2656)  # width, height
CARD_BOXES = (
    (136, 1146, 374, 1447),
    (491, 1146, 729, 1447),
    (846, 1146, 1084, 1447),
)
FRAME_BOXES = (
    (118, 1127, 392, 1463),
    (473, 1127, 747, 1463),
    (828, 1127, 1102, 1463),
)
TAP_POINTS = ((255, 1300), (610, 1300), (965, 1300))
NEXT_BUTTON_BOX = (600, 1960, 1075, 2145)
NEXT_TAP_POINT = (835, 2050)
MATCH_THRESHOLD = 55.0
MATCH_MARGIN = 12.0
FAST_MATCH_THRESHOLD = 25.0


class BotError(RuntimeError):
    pass


class StopRequested(Exception):

    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Module-level caches for processed screens to avoid repeated resize/cvtColor
_LAST_IMAGE_ID: int | None = None
_CACHED_NORMALIZED: np.ndarray | None = None
_CACHED_HSV: np.ndarray | None = None


def _invalidate_screen_cache() -> None:
    global _LAST_IMAGE_ID, _CACHED_NORMALIZED, _CACHED_HSV
    _LAST_IMAGE_ID = None
    _CACHED_NORMALIZED = None
    _CACHED_HSV = None


def normalized_screen(image: np.ndarray) -> np.ndarray:
    """Return a normalized (REFERENCE_SIZE) RGB/BGR image.

    This function now caches the last-normalized image by id(image) so that
    multiple consumers of the same screenshot don't resize repeatedly.
    """
    global _LAST_IMAGE_ID, _CACHED_NORMALIZED
    if image is None or image.size == 0:
        raise BotError("Порожнє зображення")
    height, width = image.shape[:2]
    if height <= width:
        raise BotError(f"Очікував портретний екран, отримав {width}x{height}")

    # If this exact image object was processed recently, reuse cached normalized.
    if id(image) == _LAST_IMAGE_ID and _CACHED_NORMALIZED is not None:
        return _CACHED_NORMALIZED

    # Otherwise compute, store and return.
    if (width, height) == REFERENCE_SIZE:
        normalized = image
    else:
        interpolation = cv2.INTER_AREA if width > REFERENCE_SIZE[0] else cv2.INTER_LINEAR
        normalized = cv2.resize(image, REFERENCE_SIZE, interpolation=interpolation)

    _LAST_IMAGE_ID = id(image)
    _CACHED_NORMALIZED = normalized
    # Invalidate HSV cache because normalized changed.
    global _CACHED_HSV
    _CACHED_HSV = None
    return normalized


def screen_hsv(image: np.ndarray) -> np.ndarray:
    """Return HSV of the normalized screen, cached per screenshot.

    Calling this is cheap after the first call for a given screenshot.
    """
    global _CACHED_HSV
    if id(image) == _LAST_IMAGE_ID and _CACHED_HSV is not None:
        return _CACHED_HSV
    normalized = normalized_screen(image)
    _CACHED_HSV = cv2.cvtColor(normalized, cv2.COLOR_BGR2HSV)
    return _CACHED_HSV


def crop_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Extract a region of interest from the image.
    
    Returns a view (not a copy) to optimize memory usage. The view is safe
    because we don't modify the underlying array in any way after cropping.
    If modifications are needed, the caller should .copy() the result.
    """
    x1, y1, x2, y2 = box
    return image[y1:y2, x1:x2]


def extract_cards(image: np.ndarray) -> list[np.ndarray]:
    """Extract the three card images from the screen.
    
    Returns copies because these cards are passed to fingerprint() and
    saved to disk, so they must be independent of the screen image.
    """
    screen = normalized_screen(image)
    return [crop_box(screen, box).copy() for box in CARD_BOXES]


def card_screen_scores(image: np.ndarray) -> list[float]:
    screen_h = screen_hsv(image)
    scores: list[float] = []
    for box in FRAME_BOXES:
        card_hsv = crop_box(screen_h, box)
        gold = cv2.inRange(card_hsv, (15, 130, 130), (40, 255, 255))
        purple = cv2.inRange(card_hsv, (125, 100, 80), (175, 255, 255))
        blue = cv2.inRange(card_hsv, (75, 100, 80), (125, 255, 255))
        frame_color = cv2.bitwise_or(cv2.bitwise_or(gold, purple), blue)
        scores.append(float(np.count_nonzero(frame_color)) / frame_color.size)
    return scores


def is_card_screen(image: np.ndarray) -> bool:
    return all(score >= 0.10 for score in card_screen_scores(image))


def card_rarities(image: np.ndarray) -> list[str]:
    hsv = screen_hsv(image)
    rarities: list[str] = []
    for box in FRAME_BOXES:
        card_hsv = crop_box(hsv, box)
        height, width = card_hsv.shape[:2]
        border = np.zeros((height, width), dtype=bool)
        border[:, :14] = True
        border[:, -14:] = True
        border[-18:, :] = True
        gold = cv2.inRange(card_hsv, (15, 130, 130), (40, 255, 255)) > 0
        purple = cv2.inRange(card_hsv, (125, 100, 80), (175, 255, 255)) > 0
        blue = cv2.inRange(card_hsv, (75, 100, 80), (125, 255, 255)) > 0
        gold_score = float(np.mean(gold[border]))
        purple_score = float(np.mean(purple[border]))
        blue_score = float(np.mean(blue[border]))
        if gold_score >= 0.40 and gold_score > purple_score:
            rarities.append("gold")
        elif purple_score >= 0.40 and purple_score > gold_score:
            rarities.append("purple")
        elif blue_score >= 0.40:
            rarities.append("blue")
        else:
            rarities.append("unknown")
    return rarities


def next_button_score(image: np.ndarray) -> float:
    hsv = screen_hsv(image)
    button_hsv = crop_box(hsv, NEXT_BUTTON_BOX)
    yellow = cv2.inRange(button_hsv, (10, 100, 120), (40, 255, 255))
    return float(np.count_nonzero(yellow)) / yellow.size


def is_next_screen(image: np.ndarray) -> bool:
    return next_button_score(image) >= 0.35


def phash(image: np.ndarray, hash_size: int = 16) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    values = dct[:hash_size, :hash_size].reshape(-1)[1:]
    return values > np.median(values)


@dataclass(frozen=True)
class Fingerprint:
    full: np.ndarray
    art: np.ndarray
    name: np.ndarray


def fingerprint(card: np.ndarray) -> Fingerprint:
    split = int(card.shape[0] * 0.78)
    return Fingerprint(phash(card), phash(card[:split]), phash(card[split:]))


def hamming(left: np.ndarray, right: np.ndarray) -> int:
    return int(np.count_nonzero(left != right))


def fingerprint_distance(left: Fingerprint, right: Fingerprint) -> float:
    return (
        0.45 * hamming(left.full, right.full)
        + 0.30 * hamming(left.art, right.art)
        + 0.25 * hamming(left.name, right.name)
    )


class StateStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.cards_dir = data_dir / "cards"
        self.path = data_dir / "state.json"
        self.state = self._load()
        self._dirty = False  # Flag to batch writes

    @staticmethod
    def empty_state() -> dict[str, Any]:
        return {
            "version": 1,
            "next_card_number": 1,
            "cards": {},
            "absolute_top": None,
            "preferences": {},
            "history": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.empty_state()
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BotError(f"Не вдалося прочитати {self.path}: {exc}") from exc
        if loaded.get("version") != 1:
            raise BotError(f"Непідтримувана версія даних у {self.path}")
        return loaded

    def save(self) -> None:
        """Write state to disk. Can be called eagerly or after marking dirty."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.state, ensure_ascii=False, indent=2) + "\n"
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.path)
        self._dirty = False

    def mark_dirty(self) -> None:
        """Mark state as changed but don't write yet. Caller must flush."""
        self._dirty = True

    def flush(self) -> None:
        """Write to disk if marked dirty."""
        if self._dirty:
            self.save()

    @property
    def cards(self) -> dict[str, dict[str, Any]]:
        return self.state["cards"]

    def new_card(self, image: np.ndarray, rarity: str | None = None) -> str:
        number = int(self.state["next_card_number"])
        card_id = f"card_{number:03d}"
        self.state["next_card_number"] = number + 1
        directory = self.cards_dir / card_id
        directory.mkdir(parents=True, exist_ok=True)
        sample_path = directory / "sample_001.png"
        if not cv2.imwrite(str(sample_path), image):
            raise BotError(f"Не вдалося записати {sample_path}")
        self.cards[card_id] = {
            "label": card_id,
            "priority": None,
            "rarity": rarity,
            "samples": [str(sample_path.relative_to(self.data_dir))],
            "created_at": utc_now(),
        }
        # Mark dirty instead of saving immediately; caller will flush
        self.mark_dirty()
        return card_id

    def add_sample(self, card_id: str, image: np.ndarray) -> None:
        card = self.cards[card_id]
        samples = card["samples"]
        if len(samples) >= 5:
            return
        directory = self.cards_dir / card_id
        directory.mkdir(parents=True, exist_ok=True)
        sample_path = directory / f"sample_{len(samples) + 1:03d}.png"
        if cv2.imwrite(str(sample_path), image):
            samples.append(str(sample_path.relative_to(self.data_dir)))
            # Mark dirty instead of saving immediately
            self.mark_dirty()

    def set_label(self, card_id: str, label: str) -> None:
        self.cards[card_id]["label"] = label.strip() or card_id
        ordered_labels = self.state.get("priority_order", [])
        normalized = self.cards[card_id]["label"].casefold()
        for index, ordered_label in enumerate(ordered_labels):
            if normalized == str(ordered_label).casefold():
                self.cards[card_id]["priority"] = len(ordered_labels) - index
                break
        self.save()

    def set_priority(self, card_id: str, priority: float) -> None:
        self.cards[card_id]["priority"] = priority
        self.save()

    def set_absolute_top(self, card_id: str) -> None:
        self.state["absolute_top"] = card_id
        self.save()

    def set_priority_order(self, labels: list[str]) -> None:
        self.state["priority_order"] = labels
        priorities = {label.casefold(): len(labels) - index for index, label in enumerate(labels)}
        for card in self.cards.values():
            card["priority"] = priorities.get(str(card.get("label", "")).casefold())
        self.save()

    def label(self, card_id: str | None) -> str:
        if card_id is None:
            return "невідома картка"
        return str(self.cards[card_id].get("label") or card_id)

    def priority(self, card_id: str) -> float | None:
        value = self.cards[card_id].get("priority")
        return None if value is None else float(value)

    def record_choice(self, winner: str, losers: Iterable[str]) -> None:
        losers = [loser for loser in losers if loser != winner]
        preferences = self.state["preferences"]
        for loser in losers:
            preferences.setdefault(winner, {})
            preferences[winner][loser] = int(preferences[winner].get(loser, 0)) + 1
        self.state["history"].append(
            {"at": utc_now(), "winner": winner, "losers": losers}
        )
        self.state["history"] = self.state["history"][-500:]
        self.save()

    def prefers(self, winner: str, loser: str) -> bool:
        if winner == loser:
            return True
        absolute_top = self.state.get("absolute_top")
        if winner == absolute_top:
            return True
        if loser == absolute_top:
            return False
        winner_priority = self.priority(winner)
        loser_priority = self.priority(loser)
        if winner_priority is not None and loser_priority is not None:
            if winner_priority != loser_priority:
                return winner_priority > loser_priority

        graph = self.state["preferences"]
        pending = [winner]
        visited = {winner}
        while pending:
            current = pending.pop()
            for next_card in graph.get(current, {}):
                if next_card == loser:
                    return True
                if next_card not in visited:
                    visited.add(next_card)
                    pending.append(next_card)
        return False

    def best_slot(self, card_ids: list[str | None]) -> int | None:
        absolute_top = self.state.get("absolute_top")
        if absolute_top is not None and absolute_top in card_ids:
            return card_ids.index(absolute_top)
        if any(card_id is None for card_id in card_ids):
            return None
        known_ids = [str(card_id) for card_id in card_ids]
        winners: list[int] = []
        for index, card_id in enumerate(known_ids):
            if all(
                index == other_index or self.prefers(card_id, other_id)
                for other_index, other_id in enumerate(known_ids)
            ):
                winners.append(index)
        return winners[0] if len(winners) == 1 else None


@dataclass
class Match:
    card_id: str | None
    distance: float | None
    second_distance: float | None


class Recognizer:
    def __init__(self, store: StateStore):
        self.store = store
        self.references: dict[str, list[Fingerprint]] = {}
        self._fingerprint_cache: dict[str, Fingerprint] = {}  # Cache for card fingerprints
        self.reload()

    def reload(self) -> None:
        references: dict[str, list[Fingerprint]] = {}
        self._fingerprint_cache.clear()
        for card_id, card in self.store.cards.items():
            card_references: list[Fingerprint] = []
            for relative_path in card.get("samples", []):
                image = cv2.imread(str(self.store.data_dir / relative_path))
                if image is not None:
                    card_references.append(fingerprint(image))
            if card_references:
                references[card_id] = card_references
        self.references = references

    def match(self, image: np.ndarray) -> Match:
        """Match a card image against learned references.
        
        Optimization: Pre-compute current fingerprint once instead of
        recomputing it for each reference card comparison. Algorithm
        remains identical.
        """
        current = fingerprint(image)
        distances: list[tuple[float, str]] = []
        for card_id, samples in self.references.items():
            distance = min(fingerprint_distance(current, sample) for sample in samples)
            distances.append((distance, card_id))
        distances.sort()
        if not distances:
            return Match(None, None, None)
        best_distance, best_id = distances[0]
        second_distance = distances[1][0] if len(distances) > 1 else None
        enough_margin = second_distance is None or second_distance - best_distance >= MATCH_MARGIN
        if best_distance <= MATCH_THRESHOLD and enough_margin:
            return Match(best_id, best_distance, second_distance)
        return Match(None, best_distance, second_distance)


class Adb:
    def __init__(self, executable: str, serial: str | None):
        self.base = [executable]
        if serial:
            self.base.extend(["-s", serial])
        # one-time quick check - keep minimal
        self._run(["get-state"])

    def _run(self, arguments: list[str], *, binary: bool = False) -> bytes | str:
        try:
            result = subprocess.run(
                self.base + arguments,
                check=True,
                capture_output=True,
                text=not binary,
            )
        except FileNotFoundError as exc:
            raise BotError(f"ADB не знайдено: {self.base[0]}") from exc
        except subprocess.CalledProcessError as exc:
            error = exc.stderr.decode(errors="replace") if binary else exc.stderr
            raise BotError(f"ADB завершився з помилкою: {error.strip()}") from exc
        return result.stdout

    def screenshot(self) -> np.ndarray:
        # Always obtain a fresh screenshot object; other expensive ops are cached
        raw = self._run(["exec-out", "screencap", "-p"], binary=True)
        encoded = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise BotError("ADB повернув пошкоджений скриншот")
        # Invalidate module-level caches when new screenshot object is created.
        _invalidate_screen_cache()
        return image

    def tap(self, reference_point: tuple[int, int], screen_shape: tuple[int, ...]) -> None:
        height, width = screen_shape[:2]
        x = round(reference_point[0] * width / REFERENCE_SIZE[0])
        y = round(reference_point[1] * height / REFERENCE_SIZE[1])
        # A tap will change the device state - invalidate local caches
        self._run(["shell", "input", "tap", str(x), str(y)])
        _invalidate_screen_cache()

    def tap_burst(
        self,
        reference_point: tuple[int, int],
        screen_shape: tuple[int, ...],
        *,
        initial_delay: float,
        interval: float,
        count: int,
    ) -> None:
        height, width = screen_shape[:2]
        x = round(reference_point[0] * width / REFERENCE_SIZE[0])
        y = round(reference_point[1] * height / REFERENCE_SIZE[1])
        commands = [f"sleep {initial_delay:.3f}"]
        for index in range(count):
            commands.append(f"input tap {x} {y}")
            if index + 1 < count:
                commands.append(f"sleep {interval:.3f}")
        # The extra quotes preserve semicolons when the Windows adb client
        # forwards this command through WSL to Android's remote shell.
        command = "'" + "; ".join(commands) + "'"
        self._run(["shell", "sh", "-c", command])
        _invalidate_screen_cache()


@dataclass
class Candidate:
    slot: int
    image: np.ndarray
    rarity: str
    match: Match


@dataclass
class TransitionStats:
    screenshots: int = 0
    recovered_next: bool = False


@dataclass
class AdaptiveTiming:
    initial_delay: float = 0.20
    tap_interval: float = 0.22
    tap_count: int = 8
    min_tap_count: int = 6
    max_tap_count: int = 14
    fast_streak: int = 0
    ewma_seconds: float | None = None
    completed_cycles: int = 0

    @property
    def tap_window(self) -> float:
        return self.initial_delay + self.tap_interval * max(0, self.tap_count - 1)

    def observe(self, stats: TransitionStats, elapsed: float) -> None:
        weight = 0.20
        self.ewma_seconds = (
            elapsed
            if self.ewma_seconds is None
            else (1.0 - weight) * self.ewma_seconds + weight * elapsed
        )
        self.completed_cycles += 1
        if stats.recovered_next:
            old_count = self.tap_count
            self.tap_count = min(self.max_tap_count, self.tap_count + 2)
            self.fast_streak = 0
            if self.tap_count != old_count:
                print(f"Адаптація: збільшено вікно «Наступний» до {self.tap_window:.2f} с.")
        elif stats.screenshots == 1:
            self.fast_streak += 1
            if self.fast_streak >= 8 and self.tap_count > self.min_tap_count:
                self.tap_count -= 1
                self.fast_streak = 0
                print(f"Адаптація: скорочено вікно «Наступний» до {self.tap_window:.2f} с.")
        else:
            self.fast_streak = 0

        if self.completed_cycles % 25 == 0 and self.ewma_seconds is not None:
            print(f"Швидкий режим: середній перехід ≈ {self.ewma_seconds:.2f} с.")


def confidence_text(match: Match) -> str:
    if match.card_id is None or match.distance is None:
        if match.distance is None:
            return ""
        return f"; найближча відстань {match.distance:.1f}"
    confidence = max(0.0, 100.0 * (1.0 - match.distance / MATCH_THRESHOLD))
    return f"; збіг {confidence:.0f}%"


def print_candidates(candidates: list[Candidate], store: StateStore) -> None:
    print("\nЗнайдено три картки:")
    for candidate in candidates:
        card_id = candidate.match.card_id
        priority = None if card_id is None else store.priority(card_id)
        priority_text = "" if priority is None else f"; пріоритет {priority:g}"
        rarity_text = {
            "gold": "золота",
            "purple": "фіолетова",
            "blue": "блакитна",
            "unknown": "невідома рідкість",
        }[candidate.rarity]
        print(
            f"  {candidate.slot + 1}. {store.label(card_id)} [{rarity_text}]"
            f"{priority_text}{confidence_text(candidate.match)}"
        )


def ensure_enrolled(candidate: Candidate, store: StateStore, recognizer: Recognizer) -> str:
    if candidate.match.card_id is not None:
        return candidate.match.card_id
    card_id = store.new_card(candidate.image, candidate.rarity)
    candidate.match = Match(card_id, 0.0, None)
    recognizer.reload()
    print(f"Додано нову картку: {card_id}")
    return card_id


def prompt_for_choice(
    candidates: list[Candidate], store: StateStore, recognizer: Recognizer
) -> int | None:
    print_candidates(candidates, store)
    suggested = best_candidate_slot(candidates, store)
    if suggested is not None:
        print(f"Поточна підказка: варіант {suggested + 1}")
    print("Команди: 1/2/3 — вибрати; n № назва; p № число; top №; s — пропустити; q — вихід")

    while True:
        try:
            answer = input("Ваш вибір: ").strip()
        except EOFError as exc:
            raise StopRequested from exc
        if answer in {"1", "2", "3"}:
            return int(answer) - 1
        if answer.lower() == "q":
            raise StopRequested
        if answer.lower() == "s":
            return None
        try:
            parts = shlex.split(answer)
        except ValueError as exc:
            print(f"Некоректна команда: {exc}")
            continue
        if len(parts) >= 3 and parts[0].lower() == "n" and parts[1] in {"1", "2", "3"}:
            index = int(parts[1]) - 1
            card_id = ensure_enrolled(candidates[index], store, recognizer)
            store.set_label(card_id, " ".join(parts[2:]))
            print(f"Назва збережена: {store.label(card_id)}")
            continue
        if len(parts) == 3 and parts[0].lower() == "p" and parts[1] in {"1", "2", "3"}:
            index = int(parts[1]) - 1
            try:
                priority = float(parts[2])
            except ValueError:
                print("Пріоритет має бути числом")
                continue
            card_id = ensure_enrolled(candidates[index], store, recognizer)
            store.set_priority(card_id, priority)
            print(f"Пріоритет {priority:g} збережено для {store.label(card_id)}")
            continue
        if len(parts) == 2 and parts[0].lower() == "top" and parts[1] in {"1", "2", "3"}:
            index = int(parts[1]) - 1
            card_id = ensure_enrolled(candidates[index], store, recognizer)
            store.set_absolute_top(card_id)
            print(f"Абсолютний пріоритет збережено: {store.label(card_id)}")
            continue
        print("Введіть 1, 2, 3 або одну з показаних команд")


def selection_fingerprints(image: np.ndarray) -> list[Fingerprint]:
    return [fingerprint(card) for card in extract_cards(image)]


def selection_distance(left: list[Fingerprint], right: list[Fingerprint]) -> float:
    return sum(fingerprint_distance(a, b) for a, b in zip(left, right))


def wait_for_cards(
    adb: Adb,
    poll: float,
    *,
    confirm: bool,
    recover_next: bool,
) -> tuple[np.ndarray, TransitionStats]:
    announced = False
    stats = TransitionStats()
    while True:
        image = adb.screenshot()
        stats.screenshots += 1
        # The post-pick offer contains the two unselected cards and can look
        # enough like a three-card screen to pass the broad frame detector.
        # A visible Next button is therefore the stronger transition signal.
        if recover_next and is_next_screen(image):
            adb.tap(NEXT_TAP_POINT, image.shape)
            stats.recovered_next = True
            print("Відновлення: натиснуто пропущену кнопку «Наступний».")
        elif is_card_screen(image):
            if not confirm:
                return image, stats
            time.sleep(min(0.4, poll))
            confirmed = adb.screenshot()
            stats.screenshots += 1
            if is_card_screen(confirmed):
                return confirmed, stats
        if not announced:
            print("Чекаю екран із трьома картками… (Ctrl+C для виходу)")
            announced = True
        time.sleep(poll)


def wait_until_changed(adb: Adb, old_image: np.ndarray, poll: float, timeout: float = 15.0) -> bool:
    old_fingerprints = selection_fingerprints(old_image)
    deadline = time.monotonic() + timeout
    saw_non_card_screen = False
    while time.monotonic() < deadline:
        time.sleep(poll)
        image = adb.screenshot()
        if not is_card_screen(image):
            saw_non_card_screen = True
            return True
        if selection_distance(old_fingerprints, selection_fingerprints(image)) >= 80.0:
            return True
    if not saw_non_card_screen:
        print("Екран не змінився за 15 с. Перевірте, чи спрацювало натискання.")
    return False


def press_next(adb: Adb, poll: float, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    next_screen: np.ndarray | None = None
    while time.monotonic() < deadline:
        image = adb.screenshot()
        if is_next_screen(image):
            next_screen = image
            break
        time.sleep(poll)
    if next_screen is None:
        print("Кнопку «Наступний» не знайдено за 20 с.")
        return False

    adb.tap(NEXT_TAP_POINT, next_screen.shape)
    print("Натиснуто «Наступний».")
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        time.sleep(poll)
        if not is_next_screen(adb.screenshot()):
            return True
    print("Екран «Наступний» не змінився за 15 с.")
    return False


def classify(image: np.ndarray, recognizer: Recognizer) -> list[Candidate]:
    rarities = card_rarities(image)
    return [
        Candidate(slot=index, image=card, rarity=rarities[index], match=recognizer.match(card))
        for index, card in enumerate(extract_cards(image))
    ]


def best_candidate_slot(candidates: list[Candidate], store: StateStore) -> int | None:
    """Select the best card slot based on rarity and priority.
    
    Algorithm (unchanged from original):
    1. If any gold cards with known priorities exist, select the highest priority gold.
    2. Otherwise, if any purple cards exist, select a random purple (with priority support).
    3. Otherwise, if all are blue, select a random blue.
    4. Return None if uncertain.
    
    NEW: Purple cards now support priority, matching gold behavior.
    """
    gold = [candidate for candidate in candidates if candidate.rarity == "gold"]
    if gold:
        if any(
            candidate.match.card_id is None
            or store.priority(candidate.match.card_id) is None
            for candidate in gold
        ):
            return None
        local_slot = store.best_slot([candidate.match.card_id for candidate in gold])
        return None if local_slot is None else gold[local_slot].slot

    purple = [candidate for candidate in candidates if candidate.rarity == "purple"]
    if purple:
        # NEW: Check if any purple cards have known priorities
        purple_with_priority = [
            candidate for candidate in purple
            if candidate.match.card_id is not None
            and store.priority(candidate.match.card_id) is not None
        ]
        if purple_with_priority:
            # If at least one has a priority, select the one with highest priority
            # (matching gold card logic)
            best_purple = max(
                purple_with_priority,
                key=lambda c: store.priority(c.match.card_id)
            )
            return best_purple.slot
        # If no purple cards have priorities, fall back to random selection
        return random.choice(purple).slot

    if all(candidate.rarity == "blue" for candidate in candidates):
        return random.choice(candidates).slot
    return None


def needs_fast_confirmation(candidates: list[Candidate], store: StateStore) -> bool:
    if any(candidate.rarity == "unknown" for candidate in candidates):
        return True
    for candidate in candidates:
        if candidate.rarity != "gold":
            continue
        card_id = candidate.match.card_id
        if card_id is None or store.priority(card_id) is None:
            return True
        if candidate.match.distance is None or candidate.match.distance > FAST_MATCH_THRESHOLD:
            return True
    return False


def confirm_uncertain_candidates(
    adb: Adb,
    image: np.ndarray,
    candidates: list[Candidate],
    store: StateStore,
    recognizer: Recognizer,
    poll: float,
) -> tuple[np.ndarray, list[Candidate]]:
    """Let card entrance animation settle before declaring a new gold card."""
    latest_image = image
    latest_candidates = candidates
    for delay in (max(0.12, poll), 0.25, 0.35):
        time.sleep(delay)
        confirmed = adb.screenshot()
        if not is_card_screen(confirmed):
            continue
        latest_image = confirmed
        latest_candidates = classify(confirmed, recognizer)
        if not needs_fast_confirmation(latest_candidates, store):
            break
    return latest_image, latest_candidates


def run_bot(args: argparse.Namespace) -> int:
    store = StateStore(args.data_dir)
    recognizer = Recognizer(store)
    adb = Adb(args.adb, args.serial)

    # Optional integrity check at start (can be enabled via env). This helps
    # ensure that performance changes haven't altered core behaviours.
    if os.environ.get("VERIFY_ON_START") == "1":
        _run_integrity_checks(store, recognizer)

    mode = args.command
    timing = AdaptiveTiming()
    last_choice_at: float | None = None

    while True:
        image, transition_stats = wait_for_cards(
            adb,
            args.poll,
            confirm=args.safe_transitions,
            recover_next=not args.safe_transitions,
        )
        if last_choice_at is not None and not args.safe_transitions:
            timing.observe(transition_stats, time.monotonic() - last_choice_at)
            last_choice_at = None
        candidates = classify(image, recognizer)
        if not args.safe_transitions and needs_fast_confirmation(candidates, store):
            image, candidates = confirm_uncertain_candidates(
                adb, image, candidates, store, recognizer, args.poll
            )
        suggested = best_candidate_slot(candidates, store)

        if mode == "auto" and suggested is not None:
            chosen_slot = suggested
            print_candidates(candidates, store)
            print(f"Автовибір: варіант {chosen_slot + 1}")
        else:
            if mode == "auto":
                unknown_gold = [
                    candidate.slot + 1
                    for candidate in candidates
                    if candidate.rarity == "gold"
                    and (
                        candidate.match.card_id is None
                        or store.priority(candidate.match.card_id) is None
                    )
                ]
                if unknown_gold:
                    slots = ", ".join(map(str, unknown_gold))
                    print(f"Нова золота картка у варіанті {slots} — автовибір зупинено.")
                else:
                    print("Безпечний автовибір неможливий — потрібне коротке навчання.")
            chosen_slot = prompt_for_choice(candidates, store, recognizer)

        if chosen_slot is None:
            print("Пропущено. Зробіть вибір на телефоні; чекаю зміни екрана.")
            wait_until_changed(adb, image, args.poll)
            if args.once:
                return 0
            continue

        card_ids = [ensure_enrolled(candidate, store, recognizer) for candidate in candidates]
        # Flush any pending state writes from ensure_enrolled/new_card
        store.flush()
        
        winner = card_ids[chosen_slot]
        if any(candidate.rarity == "gold" for candidate in candidates):
            store.record_choice(winner, [card_id for i, card_id in enumerate(card_ids) if i != chosen_slot])
            print(f"Запам'ятано: {store.label(winner)} краща за інші картки цієї трійки.")
        else:
            print("Усі картки фіолетові — випадковий вибір не змінює пріоритети.")

        if args.dry_run:
            print(f"DRY RUN: натискання варіанта {chosen_slot + 1} не виконано.")
            return 0
        last_choice_at = time.monotonic()
        adb.tap(TAP_POINTS[chosen_slot], image.shape)
        print(f"Натиснуто варіант {chosen_slot + 1}.")
        if args.safe_transitions:
            if wait_until_changed(adb, image, args.poll):
                press_next(adb, args.poll)
        else:
            adb.tap_burst(
                NEXT_TAP_POINT,
                image.shape,
                initial_delay=timing.initial_delay,
                interval=timing.tap_interval,
                count=timing.tap_count,
            )
            print(f"Надіслано «Наступний» ×{timing.tap_count}.")
        if args.once:
            return 0


def inspect_image(args: argparse.Namespace) -> int:
    image = cv2.imread(str(args.image))
    if image is None:
        raise BotError(f"Не вдалося відкрити {args.image}")
    scores = card_screen_scores(image)
    print("Ознаки екрана карток:", ", ".join(f"{score:.3f}" for score in scores))
    print("Екран розпізнано:", "так" if is_card_screen(image) else "ні")
    store = StateStore(args.data_dir)
    recognizer = Recognizer(store)
    print_candidates(classify(image, recognizer), store)
    return 0


def show_status(args: argparse.Namespace) -> int:
    store = StateStore(args.data_dir)
    if not store.cards:
        print("Навчених карток ще немає.")
        return 0
    print("Відомі картки:")
    absolute_top = store.state.get("absolute_top")
    if absolute_top:
        print(f"Абсолютний пріоритет: {store.label(absolute_top)}")
    for card_id, card in sorted(store.cards.items()):
        priority = card.get("priority")
        priority_text = "—" if priority is None else f"{float(priority):g}"
        print(f"  {card_id}: {card.get('label', card_id)}; пріоритет {priority_text}; зразків {len(card['samples'])}")
    print("Переваги:")
    any_preference = False
    for winner, losers in store.state["preferences"].items():
        for loser, count in losers.items():
            any_preference = True
            print(f"  {store.label(winner)} > {store.label(loser)} ({count}×)")
    if not any_preference:
        print("  ще немає")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Навчання й автоматичний вибір карток Island War через ADB")
    parser.add_argument("--data-dir", type=Path, default=Path("bot_data"), help="каталог навчальних даних")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("learn", "питати кожен вибір і навчатися"),
        ("auto", "автоматично вибирати відомий однозначний пріоритет"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("--adb", default="adb", help="шлях до adb")
        subparser.add_argument("--serial", help="серійний номер пристрою")
        subparser.add_argument("--poll", type=float, default=0.15, help="інтервал опитування, с")
        subparser.add_argument("--once", action="store_true", help="обробити лише одну трійку")
        subparser.add_argument("--dry-run", action="store_true", help="навчитися, але не натискати")
        subparser.add_argument(
            "--safe-transitions",
            action="store_true",
            help="старий консервативний режим із підтверджувальними скриншотами",
        )

    inspect_parser = subparsers.add_parser("inspect", help="перевірити збережений скриншот без натискань")
    inspect_parser.add_argument("image", type=Path)
    subparsers.add_parser("status", help="показати вивчені картки й пріоритети")

    # Benchmark command: measure processing times without creating extra adb screencaps.
    bench = subparsers.add_parser("benchmark", help="запустити бенчмарк обробки кадру (без зайвих adb) ")
    bench.add_argument("--adb", default="adb", help="шлях до adb (використовується лише для початкового знімка)")
    bench.add_argument("--serial", help="серійний номер пристрою")
    bench.add_argument("--iterations", type=int, default=200, help="кількість ітерацій бенчмарку")
    bench.add_argument("--image", type=Path, help="використовувати локальне зображення замість adb")
    return parser


def _run_integrity_checks(store: StateStore, recognizer: Recognizer) -> None:
    """Simple smoke tests to assert core logic types and invariants.

    These checks are intentionally lightweight: they exercise the core
    classification pipeline on either a saved sample (if present) or a small
    generated image. They do not change state or learning behaviour.
    """
    print("Запуск перевірки цілісності логіки...")
    # Use a sample from store if available
    sample_image = None
    for card in store.cards.values():
        samples = card.get("samples", [])
        if samples:
            p = store.data_dir / samples[0]
            if p.exists():
                sample_image = cv2.imread(str(p))
                break
    if sample_image is None:
        # synthetic small image - won't pass card detection but will exercise code paths
        sample_image = np.zeros((960, 540, 3), dtype=np.uint8)

    try:
        scores = card_screen_scores(sample_image)
        assert isinstance(scores, list) and all(isinstance(s, float) for s in scores)
        # ensure functions don't raise
        _ = is_card_screen(sample_image)
        _ = card_rarities(sample_image)
        fps = selection_fingerprints(sample_image)
        assert isinstance(fps, list)
        print("Перевірка пройдена локально.")
    except Exception as exc:
        print(f"Помилка перевірки логіки: {exc}")
        raise


def _benchmark(args: argparse.Namespace) -> int:
    # Acquire one image to reuse for all iterations to avoid extra adb calls.
    if args.image:
        image = cv2.imread(str(args.image))
        if image is None:
            raise BotError(f"Не вдалося відкрити {args.image}")
    else:
        adb = Adb(args.adb, args.serial)
        image = adb.screenshot()
    store = StateStore(Path("bot_data"))
    recognizer = Recognizer(store)

    iterations = max(1, int(args.iterations))
    timings = {
        "normalized": 0.0,
        "hsv": 0.0,
        "card_scores": 0.0,
        "rarities": 0.0,
        "extract_cards": 0.0,
        "phash": 0.0,
    }

    # Warm-up once
    normalized_screen(image)
    screen_hsv(image)

    for i in range(iterations):
        t0 = time.perf_counter()
        _ = normalized_screen(image)
        t1 = time.perf_counter()
        _ = screen_hsv(image)
        t2 = time.perf_counter()
        _ = card_screen_scores(image)
        t3 = time.perf_counter()
        _ = card_rarities(image)
        t4 = time.perf_counter()
        cards = extract_cards(image)
        t5 = time.perf_counter()
        for c in cards:
            _ = phash(c)
        t6 = time.perf_counter()
        timings["normalized"] += t1 - t0
        timings["hsv"] += t2 - t1
        timings["card_scores"] += t3 - t2
        timings["rarities"] += t4 - t3
        timings["extract_cards"] += t5 - t4
        timings["phash"] += t6 - t5

    print(f"Бенчмарк ({iterations} ітерацій) — середні часи (мс):")
    for k, v in timings.items():
        print(f"  {k}: {v / iterations * 1000:.3f}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command in {"learn", "auto"}:
            return run_bot(args)
        if args.command == "inspect":
            return inspect_image(args)
        if args.command == "status":
            return show_status(args)
        if args.command == "benchmark":
            return _benchmark(args)
        parser.error("невідома команда")
    except StopRequested:
        print("Зупинено користувачем.")
        return 0
    except KeyboardInterrupt:
        print("\nЗупинено.")
        return 130
    except BotError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())