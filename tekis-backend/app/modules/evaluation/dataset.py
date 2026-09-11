"""Chargement/validation du dataset JSONL d'évaluation."""
import json
from pathlib import Path
from .contracts import EvalQuestion


def load_dataset(path: str | Path) -> list[EvalQuestion]:
    questions = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip(): continue
            payload = json.loads(line)
            try:
                questions.append(EvalQuestion(**payload))
            except TypeError as exc:
                raise ValueError(f"Question invalide ligne {line_no}: {exc}") from exc
    validate_dataset(questions)
    return questions


def validate_dataset(questions: list[EvalQuestion]) -> None:
    ids = [q.id for q in questions]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Les identifiants de questions doivent être uniques."
        )

    for q in questions:
        if not q.id or not q.question:
            raise ValueError(
                "Chaque question doit avoir id et question."
            )

        expected_chunk_ids = {
            int(chunk_id)
            for chunk_id in q.expected_chunk_ids
        }

        relevance_chunk_ids = {
            int(chunk_id)
            for chunk_id in q.relevance_grades.keys()
        }

        if q.relevance_grades and not relevance_chunk_ids.issubset(
            expected_chunk_ids
        ):
            raise ValueError(
                f"{q.id}: relevance_grades doit référencer "
                "expected_chunk_ids."
            )
