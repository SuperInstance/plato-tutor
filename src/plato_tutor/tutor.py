"""Tutor with knowledge anchors and learning progress."""

import time
from dataclasses import dataclass, field

@dataclass
class Anchor:
    topic: str
    content: str
    room: str = "default"
    depth: int = 1
    prerequisites: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    mastery: float = 0.0

class Tutor:
    def __init__(self):
        self._anchors: dict[str, Anchor] = {}
        self._progress: dict[str, float] = {}

    def add_anchor(self, topic: str, content: str, room: str = "", prerequisites: list[str] = None, depth: int = 1) -> Anchor:
        a = Anchor(topic=topic, content=content, room=room, prerequisites=prerequisites or [], depth=depth)
        self._anchors[topic] = a
        return a

    def tutor_jump(self, topic: str) -> Optional[Anchor]:
        a = self._anchors.get(topic)
        if a:
            a.access_count += 1
            return a
        return None

    def search(self, query: str, top_n: int = 5) -> list[Anchor]:
        q = query.lower()
        results = []
        for a in self._anchors.values():
            score = sum(1 for w in q.split() if w in a.content.lower()) + (1 if q in a.topic.lower() else 0)
            if score > 0: results.append((score, a))
        results.sort(key=lambda x: -x[0])
        return [a for _, a in results[:top_n]]

    def update_mastery(self, topic: str, score: float):
        old = self._progress.get(topic, 0.0)
        self._progress[topic] = old * 0.7 + score * 0.3
        if topic in self._anchors:
            self._anchors[topic].mastery = self._progress[topic]

    def get_prerequisites(self, topic: str) -> list[str]:
        a = self._anchors.get(topic)
        return a.prerequisites if a else []

    def learning_path(self, topic: str) -> list[str]:
        path, visited = [], set()
        def _walk(t):
            if t in visited: return
            visited.add(t)
            for p in self.get_prerequisites(t):
                _walk(p)
            path.append(t)
        _walk(topic)
        return path

    @property
    def stats(self) -> dict:
        mastered = sum(1 for m in self._progress.values() if m >= 0.8)
        return {"anchors": len(self._anchors), "topics_tracked": len(self._progress),
                "mastered": mastered, "avg_mastery": sum(self._progress.values()) / max(len(self._progress), 1)}

from typing import Optional
