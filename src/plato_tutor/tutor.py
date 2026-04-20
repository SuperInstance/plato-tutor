"""Tutor — adaptive learning with spaced repetition, progress tracking, quizzes."""
import time
import random
import hashlib
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

@dataclass
class Flashcard:
    id: str
    front: str
    back: str
    difficulty: Difficulty = Difficulty.BEGINNER
    tags: list[str] = field(default_factory=list)
    next_review: float = 0.0
    interval: float = 3600.0  # seconds between reviews
    ease_factor: float = 2.5
    repetitions: int = 0
    last_reviewed: float = 0.0

@dataclass
class QuizQuestion:
    id: str
    question: str
    answer: str
    options: list[str] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.BEGINNER
    explanation: str = ""

@dataclass
class StudentProgress:
    student_id: str
    cards_mastered: int = 0
    cards_learning: int = 0
    total_reviews: int = 0
    correct_answers: int = 0
    streak: int = 0
    longest_streak: int = 0
    started_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    difficulty: Difficulty = Difficulty.BEGINNER

class Tutor:
    def __init__(self):
        self._cards: dict[str, Flashcard] = {}
        self._quizzes: dict[str, QuizQuestion] = {}
        self._students: dict[str, StudentProgress] = {}
        self._review_history: list[dict] = []

    def add_card(self, front: str, back: str, difficulty: str = "beginner",
                 tags: list[str] = None) -> Flashcard:
        card_id = hashlib.md5(f"{front}{time.time()}".encode()).hexdigest()[:12]
        card = Flashcard(id=card_id, front=front, back=back,
                        difficulty=Difficulty[difficulty.upper()],
                        tags=tags or [], next_review=time.time())
        self._cards[card_id] = card
        return card

    def add_quiz(self, question: str, answer: str, options: list[str] = None,
                 difficulty: str = "beginner", explanation: str = "") -> QuizQuestion:
        qid = hashlib.md5(f"{question}{time.time()}".encode()).hexdigest()[:12]
        qq = QuizQuestion(id=qid, question=question, answer=answer,
                         options=options or [], difficulty=Difficulty[difficulty.upper()],
                         explanation=explanation)
        self._quizzes[qid] = qq
        return qq

    def review(self, student_id: str, card_id: str, quality: float) -> dict:
        """SM-2 spaced repetition. quality: 0.0 (fail) to 1.0 (perfect)."""
        card = self._cards.get(card_id)
        if not card:
            return {"error": "Card not found"}
        student = self._get_student(student_id)
        student.total_reviews += 1
        student.last_active = time.time()

        if quality >= 0.6:
            student.correct_answers += 1
            student.streak += 1
            student.longest_streak = max(student.longest_streak, student.streak)
            card.repetitions += 1
            if card.repetitions == 1:
                card.interval = 3600  # 1 hour
            elif card.repetitions == 2:
                card.interval = 86400  # 1 day
            else:
                card.interval *= card.ease_factor
            card.ease_factor = max(1.3, card.ease_factor + (0.1 - (1.0 - quality) * (0.08 + (1.0 - quality) * 0.02)))
        else:
            student.streak = 0
            card.repetitions = 0
            card.interval = 300  # 5 min retry

        card.next_review = time.time() + card.interval
        card.last_reviewed = time.time()
        self._review_history.append({"student": student_id, "card": card_id,
                                     "quality": quality, "new_interval": card.interval,
                                     "timestamp": time.time()})
        if len(self._review_history) > 1000:
            self._review_history = self._review_history[-1000:]

        mastered = card.repetitions >= 3 and card.ease_factor >= 2.0
        if mastered:
            student.cards_mastered += 1
        return {"card_id": card_id, "next_review_in_s": round(card.interval),
                "repetitions": card.repetitions, "ease": round(card.ease_factor, 2),
                "mastered": mastered}

    def take_quiz(self, student_id: str, question_id: str, answer: str) -> dict:
        qq = self._quizzes.get(question_id)
        if not qq:
            return {"error": "Question not found"}
        student = self._get_student(student_id)
        student.last_active = time.time()
        correct = answer.strip().lower() == qq.answer.strip().lower()
        result = QuizResult.CORRECT if correct else QuizResult.INCORRECT
        if correct:
            student.correct_answers += 1
            student.streak += 1
            student.longest_streak = max(student.longest_streak, student.streak)
        else:
            student.streak = 0
        student.total_reviews += 1
        return {"question_id": question_id, "result": result.value,
                "correct": correct, "explanation": qq.explanation}

    def due_cards(self, student_id: str = "", limit: int = 20) -> list[Flashcard]:
        now = time.time()
        due = [c for c in self._cards.values() if c.next_review <= now]
        due.sort(key=lambda c: c.next_review)
        return due[:limit]

    def cards_by_tag(self, tag: str) -> list[Flashcard]:
        return [c for c in self._cards.values() if tag in c.tags]

    def random_quiz(self, difficulty: str = "", n: int = 5) -> list[QuizQuestion]:
        pool = list(self._quizzes.values())
        if difficulty:
            pool = [q for q in pool if q.difficulty.value == Difficulty[difficulty.upper()].value]
        return random.sample(pool, min(n, len(pool))) if pool else []

    def _get_student(self, student_id: str) -> StudentProgress:
        if student_id not in self._students:
            self._students[student_id] = StudentProgress(student_id=student_id)
        return self._students[student_id]

    @property
    def stats(self) -> dict:
        return {"cards": len(self._cards), "quizzes": len(self._quizzes),
                "students": len(self._students), "reviews": len(self._review_history)}
