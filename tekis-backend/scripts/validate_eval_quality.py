"""Audit qualité du dataset d'évaluation TEKIS."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def load_jsonl(path: str | Path) -> list[dict]:
    questions = []

    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSON invalide ligne {line_no}: {exc}"
                ) from exc

    return questions


def add_issue(issues, qid, severity, message):
    issues.append(
        {
            "id": qid,
            "severity": severity,
            "message": message,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument(
        "--report",
        default="evaluation_quality_report.json",
    )

    args = parser.parse_args()

    questions = load_jsonl(args.dataset)
    issues = []

    ids = [q.get("id") for q in questions]

    # ---------------------------------------------------------
    # 1. IDs uniques
    # ---------------------------------------------------------

    counts = Counter(ids)

    for qid, count in counts.items():
        if count > 1:
            add_issue(
                issues,
                qid,
                "ERROR",
                f"ID dupliqué ({count} occurrences).",
            )

    # ---------------------------------------------------------
    # 2. Vérification question par question
    # ---------------------------------------------------------

    allowed_categories = {
        "factual",
        "multi_chunk",
        "memory",
        "memory_context",
        "abstention",
        "citation",
        "version",
    }

    for q in questions:

        qid = q.get("id", "<sans-id>")
        question = q.get("question", "")
        answer = q.get("reference_answer", "")

        chunk_ids = q.get("expected_chunk_ids") or []
        grades = q.get("relevance_grades") or {}

        document_ids = q.get("expected_document_ids") or []
        version_ids = q.get("expected_document_version_ids") or []

        citations = q.get("expected_citations") or []
        keywords = q.get("expected_keywords") or []

        memory_facts = q.get("expected_memory_facts") or []
        kg_facts = q.get("expected_kg_facts") or []

        abstention = bool(q.get("expects_abstention", False))

        metadata = q.get("metadata") or {}
        category = metadata.get("category")

        # -----------------------------------------------------
        # Question
        # -----------------------------------------------------

        if not isinstance(question, str) or len(question.strip()) < 15:
            add_issue(
                issues,
                qid,
                "ERROR",
                "Question absente ou trop courte.",
            )

        # -----------------------------------------------------
        # Réponse
        # -----------------------------------------------------

        if not abstention:
            if not isinstance(answer, str) or len(answer.strip()) < 10:
                add_issue(
                    issues,
                    qid,
                    "ERROR",
                    "reference_answer absente ou trop courte.",
                )

        # -----------------------------------------------------
        # Chunks
        # -----------------------------------------------------

        try:
            expected_chunks = {
                int(x)
                for x in chunk_ids
            }

            graded_chunks = {
                int(x)
                for x in grades.keys()
            }

        except (TypeError, ValueError):

            add_issue(
                issues,
                qid,
                "ERROR",
                "Identifiant de chunk non numérique.",
            )

            expected_chunks = set()
            graded_chunks = set()

        if not abstention and not expected_chunks:
            add_issue(
                issues,
                qid,
                "ERROR",
                "Question non-abstention sans expected_chunk_ids.",
            )

        if not graded_chunks.issubset(expected_chunks):
            add_issue(
                issues,
                qid,
                "ERROR",
                "relevance_grades référence des chunks "
                "absents de expected_chunk_ids.",
            )

        # -----------------------------------------------------
        # Abstention
        # -----------------------------------------------------

        if abstention and expected_chunks:
            add_issue(
                issues,
                qid,
                "WARNING",
                "Question d'abstention avec des chunks attendus.",
            )

        if category == "abstention" and not abstention:
            add_issue(
                issues,
                qid,
                "ERROR",
                "Catégorie abstention mais "
                "expects_abstention=false.",
            )

        # -----------------------------------------------------
        # Catégorie
        # -----------------------------------------------------

        if category not in allowed_categories:
            add_issue(
                issues,
                qid,
                "WARNING",
                f"Catégorie inconnue ou absente: {category!r}.",
            )

        # -----------------------------------------------------
        # Multi-chunks
        # -----------------------------------------------------

        if category == "multi_chunk" and len(expected_chunks) < 2:
            add_issue(
                issues,
                qid,
                "WARNING",
                "Question multi_chunk avec moins de "
                "2 chunks attendus.",
            )

        # -----------------------------------------------------
        # Documents / versions
        # -----------------------------------------------------

        if not abstention and not document_ids:
            add_issue(
                issues,
                qid,
                "WARNING",
                "expected_document_ids vide.",
            )

        if not abstention and not version_ids:
            add_issue(
                issues,
                qid,
                "WARNING",
                "expected_document_version_ids vide.",
            )

        # -----------------------------------------------------
        # Citations
        # -----------------------------------------------------

        cited_chunks = set()

        for citation in citations:

            if not isinstance(citation, dict):
                add_issue(
                    issues,
                    qid,
                    "ERROR",
                    "Citation invalide.",
                )
                continue

            required = (
                "document_id",
                "document_version_id",
                "chunk_id",
            )

            missing = [
                field
                for field in required
                if field not in citation
            ]

            if missing:
                add_issue(
                    issues,
                    qid,
                    "ERROR",
                    "Citation sans champ(s): "
                    + ", ".join(missing),
                )
                continue

            try:
                cited_chunks.add(
                    int(citation["chunk_id"])
                )
            except (TypeError, ValueError):
                add_issue(
                    issues,
                    qid,
                    "ERROR",
                    "chunk_id de citation non numérique.",
                )

        if cited_chunks and not cited_chunks.issubset(
            expected_chunks
        ):
            add_issue(
                issues,
                qid,
                "ERROR",
                "Une citation référence un chunk "
                "non attendu.",
            )

        if category == "citation" and not citations:
            add_issue(
                issues,
                qid,
                "WARNING",
                "Catégorie citation sans expected_citations.",
            )

        # -----------------------------------------------------
        # Version
        # -----------------------------------------------------

        if category == "version" and not version_ids:
            add_issue(
                issues,
                qid,
                "WARNING",
                "Catégorie version sans document version attendu.",
            )

        # -----------------------------------------------------
        # Mémoire
        # -----------------------------------------------------

        if category in {
            "memory",
            "memory_context",
        } and not memory_facts:

            add_issue(
                issues,
                qid,
                "WARNING",
                "Question mémoire sans expected_memory_facts.",
            )

        # -----------------------------------------------------
        # KG
        # -----------------------------------------------------

        if category in {
            "kg",
            "knowledge_graph",
        } and not kg_facts:

            add_issue(
                issues,
                qid,
                "WARNING",
                "Question KG sans expected_kg_facts.",
            )

        # -----------------------------------------------------
        # Keywords
        # -----------------------------------------------------

        if not abstention and not keywords:
            add_issue(
                issues,
                qid,
                "WARNING",
                "expected_keywords vide.",
            )

        # -----------------------------------------------------
        # Détection UTF-8 / mojibake
        # -----------------------------------------------------

        mojibake_markers = (
            "Ã",
            "Â",
            "â€",
            "â€™",
            "â€œ",
            " ",
        )

        corrupted = [
            marker
            for marker in mojibake_markers
            if marker in question or marker in answer
        ]

        if corrupted:
            add_issue(
                issues,
                qid,
                "ERROR",
                "Encodage/mojibake détecté: "
                + ", ".join(sorted(set(corrupted))),
            )

        # -----------------------------------------------------
        # Question suspecte
        # -----------------------------------------------------

        suspicious_patterns = [
            r"\bsa,\s+Lubumbashi\b",
            r"\+\s+Couverture",
            r"\bque pr[ée]cise le corpus\b",
            r"\bno$",
        ]

        for pattern in suspicious_patterns:

            if re.search(
                pattern,
                question,
                re.IGNORECASE,
            ):

                add_issue(
                    issues,
                    qid,
                    "WARNING",
                    "Fragment/question suspect détecté: "
                    + pattern,
                )

        # -----------------------------------------------------
        # Longueur
        # -----------------------------------------------------

        if len(question) > 500:
            add_issue(
                issues,
                qid,
                "WARNING",
                "Question très longue (>500 caractères).",
            )

        if len(answer) > 1500:
            add_issue(
                issues,
                qid,
                "WARNING",
                "Réponse très longue (>1500 caractères).",
            )

    # ---------------------------------------------------------
    # Rapport
    # ---------------------------------------------------------

    errors = sum(
        item["severity"] == "ERROR"
        for item in issues
    )

    warnings = sum(
        item["severity"] == "WARNING"
        for item in issues
    )

    categories = Counter(
        (q.get("metadata") or {}).get(
            "category",
            "unknown",
        )
        for q in questions
    )

    status = (
        "FAIL"
        if errors
        else "REVIEW"
        if warnings
        else "PASS"
    )

    report = {
        "dataset": str(args.dataset),
        "question_count": len(questions),
        "unique_question_ids": len(set(ids)),
        "errors": errors,
        "warnings": warnings,
        "status": status,
        "categories": dict(categories),
        "issues": issues,
    }

    report_path = Path(args.report)

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ---------------------------------------------------------
    # Console
    # ---------------------------------------------------------

    print("=" * 64)
    print("AUDIT QUALITÉ DATASET TEKIS")
    print("=" * 64)

    print(f"Questions      : {len(questions)}")
    print(f"IDs uniques    : {len(set(ids))}")
    print(f"Erreurs        : {errors}")
    print(f"Avertissements : {warnings}")
    print(f"Statut         : {status}")

    print()
    print("Catégories :")

    for category, count in sorted(categories.items()):
        print(f"  - {category}: {count}")

    print()
    print(f"Rapport : {report_path}")

    if issues:

        print()
        print("Problèmes détectés :")

        for item in issues[:50]:

            print(
                f"[{item['severity']}] "
                f"{item['id']}: "
                f"{item['message']}"
            )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())