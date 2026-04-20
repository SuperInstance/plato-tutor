"""Tutor — adaptive learning with SM-2 spaced repetition, difficulty adaptation, progress tracking."""
import time
import random
import hashlib
import math
from dataclasses import dataclass, field
from typing import Optional, Callable
from collections import defaultdict
from enum import Enum

class Difficulty(Enum):
    BEGINNER = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4

class QuizResult(Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"
    SKIPPED = "skipped"

class MasteryLevel(Enum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    MASTERED = "mastered"

@dataclass
class Flashcard:
    id: str
    front: str
    back: str
    difficulty: Difficulty = Difficulty.BEGINNER
    tags: list[str] = field(default_factory=list)
    # SM-2 spaced repetition fields
    next_review: float = 0.0
    interval: float = 3600.0
    ease_factor: float = 2.5  # SM-2 EASiness factor
    repetitions: int = 0     # consecutive correct reps
    lapses: int = 0          # times forgotten
    # Metadata
    created_at: float = field(default_factory=time.time)
    last_reviewed: float = 0.0
    total_reviews: int = 0
    correct_reviews: int = 0
    mastery: MasteryLevel = MasteryLevel.NEW

@dataclass
class QuizQuestion:
    card: Flashcard
    asked_front: bool = True  # True = show front, guess back
    options: list[str] = field(default_factory=list)  # multiple choice
    correct_answer: str = ""
    shuffle_options: bool = True

@dataclass
class QuizResponse:
    question: QuizQuestion
    answer: str
    result: QuizResult
    response_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class SessionStats:
    session_id: str
    cards_studied: int = 0
    correct: int = 0
    incorrect: int = 0
    partial: int = 0
    skipped: int = 0
    avg_response_time_ms: float = 0.0
    accuracy: float = 0.0
    duration_s: float = 0.0
    difficulty_distribution: dict = field(default_factory=lambda: defaultdict(int))
    mastery_advances: int = 0

@dataclass
class ProgressReport:
    total_cards: int = 0
    by_mastery: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_difficulty: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_tag: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_reviews: int = 0
    total_correct: int = 0
    overall_accuracy: float = 0.0
    avg_ease_factor: float = 0.0
    cards_due: int = 0
    retention_rate: float = 0.0

class Tutor:
    def __init__(self, session_id: str = ""):
        self._cards: dict[str, Flashcard] = {}
        self._sessions: dict[str, list[QuizResponse]] = defaultdict(list)
        self._session_stats: dict[str, SessionStats] = {}
        self.current_session = session_id or hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

    def add_card(self, card: Flashcard) -> Flashcard:
        self._cards[card.id] = card
        return card

    def add_cards(self, cards: list[Flashcard]):
        for card in cards:
            self._cards[card.id] = card

    def get_card(self, card_id: str) -> Optional[Flashcard]:
        return self._cards.get(card_id)

    def cards_by_difficulty(self, difficulty: Difficulty) -> list[Flashcard]:
        return [c for c in self._cards.values() if c.difficulty == difficulty]

    def cards_by_mastery(self, mastery: MasteryLevel) -> list[Flashcard]:
        return [c for c in self._cards.values() if c.mastery == mastery]

    def cards_by_tag(self, tag: str) -> list[Flashcard]:
        return [c for c in self._cards.values() if tag in c.tags]

    def cards_due(self) -> list[Flashcard]:
        now = time.time()
        return [c for c in self._cards.values() if c.next_review <= now]

    def next_question(self, difficulty: Difficulty = None, tags: list[str] = None) -> Optional[QuizQuestion]:
        due = self.cards_due()
        if difficulty:
            due = [c for c in due if c.difficulty == difficulty]
        if tags:
            due = [c for c in due if any(t in c.tags for t in tags)]
        if not due:
            # No cards due — pick from learning/new
            pool = [c for c in self._cards.values() if c.mastery in (MasteryLevel.NEW, MasteryLevel.LEARNING)]
            if difficulty:
                pool = [c for c in pool if c.difficulty == difficulty]
            if not pool:
                return None
        else:
            pool = due
        # Prioritize cards with highest lapses, then oldest review
        card = min(pool, key=lambda c: (-c.lapses, c.last_reviewed))
        asked_front = random.random() > 0.3  # 70% front→back, 30% back→front
        return QuizQuestion(card=card, asked_front=asked_front)

    def generate_options(self, question: QuizQuestion, n: int = 4) -> QuizQuestion:
        correct = question.card.back if question.asked_front else question.card.front
        others = [c.back if question.asked_front else c.front
                 for c in self._cards.values() if c.id != question.card.id]
        random.shuffle(others)
        options = [correct] + others[:n - 1]
        random.shuffle(options)
        question.options = options
        question.correct_answer = correct
        return question

    def submit_answer(self, question: QuizQuestion, answer: str,
                     response_time_ms: float = 0.0) -> QuizResponse:
        correct_answer = question.card.back if question.asked_front else question.card.front
        if answer.strip().lower() == correct_answer.strip().lower():
            result = QuizResult.CORRECT
        elif any(w in correct_answer.lower() for w in answer.strip().lower().split()):
            result = QuizResult.PARTIAL
        elif not answer.strip():
            result = QuizResult.SKIPPED
        else:
            result = QuizResult.INCORRECT
        response = QuizResponse(question=question, answer=answer, result=result,
                              response_time_ms=response_time_ms)
        self._apply_sm2(question.card, result)
        self._sessions[self.current_session].append(response)
        return response

    def _apply_sm2(self, card: Flashcard, result: QuizResult):
        """SM-2 spaced repetition algorithm."""
        now = time.time()
        card.last_reviewed = now
        card.total_reviews += 1
        if result == QuizResult.CORRECT:
            card.correct_reviews += 1
            card.repetitions += 1
            if card.repetitions == 1:
                card.interval = 600.0  # 10 min
            elif card.repetitions == 2:
                card.interval = 3600.0  # 1 hour
            else:
                card.interval *= card.ease_factor
            card.next_review = now + card.interval
            # Update mastery
            if card.repetitions >= 5 and card.lapses == 0:
                card.mastery = MasteryLevel.MASTERED
            elif card.repetitions >= 2:
                card.mastery = MasteryLevel.REVIEW
            else:
                card.mastery = MasteryLevel.LEARNING
        elif result == QuizResult.INCORRECT:
            card.repetitions = 0
            card.lapses += 1
            card.interval = 60.0  # 1 min
            card.next_review = now + card.interval
            card.ease_factor = max(1.3, card.ease_factor - 0.2)
            card.mastery = MasteryLevel.LEARNING
        elif result == QuizResult.PARTIAL:
            card.interval = max(60.0, card.interval * 0.5)
            card.next_review = now + card.interval
            card.mastery = MasteryLevel.LEARNING
        # SKIPPED: no change

    def session_stats(self, session_id: str = "") -> SessionStats:
        sid = session_id or self.current_session
        responses = self._sessions.get(sid, [])
        if not responses:
            return SessionStats(session_id=sid)
        correct = sum(1 for r in responses if r.result == QuizResult.CORRECT)
        incorrect = sum(1 for r in responses if r.result == QuizResult.INCORRECT)
        partial = sum(1 for r in responses if r.result == QuizResult.PARTIAL)
        skipped = sum(1 for r in responses if r.result == QuizResult.SKIPPED)
        total_time = sum(r.response_time_ms for r in responses)
        avg_time = total_time / len(responses) if responses else 0
        diff_dist = defaultdict(int)
        for r in responses:
            diff_dist[r.question.card.difficulty.name] += 1
        duration = 0.0
        if responses:
            duration = (responses[-1].timestamp - responses[0].timestamp)
        return SessionStats(
            session_id=sid, cards_studied=len(responses),
            correct=correct, incorrect=incorrect, partial=partial, skipped=skipped,
            avg_response_time_ms=avg_time,
            accuracy=correct / len(responses) if responses else 0.0,
            duration_s=duration, difficulty_distribution=diff_dist)

    def progress(self) -> ProgressReport:
        total = len(self._cards)
        by_mastery = defaultdict(int)
        by_difficulty = defaultdict(int)
        by_tag = defaultdict(int)
        total_reviews = 0
        total_correct = 0
        total_ease = 0.0
        due = 0
        for card in self._cards.values():
            by_mastery[card.mastery.value] += 1
            by_difficulty[card.difficulty.name] += 1
            for tag in card.tags:
                by_tag[tag] += 1
            total_reviews += card.total_reviews
            total_correct += card.correct_reviews
            total_ease += card.ease_factor
            if card.next_review <= time.time():
                due += 1
        retention = total_correct / total_reviews if total_reviews > 0 else 0.0
        return ProgressReport(
            total_cards=total, by_mastery=dict(by_mastery),
            by_difficulty=dict(by_difficulty), by_tag=dict(by_tag),
            total_reviews=total_reviews, total_correct=total_correct,
            overall_accuracy=retention,
            avg_ease_factor=total_ease / total if total > 0 else 0.0,
            cards_due=due, retention_rate=retention)

    def start_session(self, session_id: str = ""):
        self.current_session = session_id or hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

    @property
    def stats(self) -> dict:
        return {"cards": len(self._cards), "sessions": len(self._sessions),
                "due": len(self.cards_due()),
                "current_session": self.current_session}
