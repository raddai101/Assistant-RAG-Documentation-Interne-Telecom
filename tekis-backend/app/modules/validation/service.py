"""
Service de validation (module `validation`, Phase 6, memoire.md §14, §17). Exécuté
entre le retrieval et l'appel au LLM (jamais après génération) : décide si les
preuves récupérées sont suffisantes pour générer une réponse, ou si l'abstention
s'impose.
"""
from app.modules.retrieval.contracts import VectorSearchResult
from app.modules.validation.confidence_scorer import ConfidenceScorer
from app.modules.validation.contradiction_detector import ContradictionDetector
from app.modules.validation.contracts import ValidationOutcome


class ValidationService:
    def __init__(
        self,
        confidence_scorer: ConfidenceScorer | None = None,
        contradiction_detector: ContradictionDetector | None = None,
        confidence_threshold: float = 0.5,
    ):
        self._confidence_scorer = confidence_scorer or ConfidenceScorer()
        self._contradiction_detector = contradiction_detector or ContradictionDetector()
        self._confidence_threshold = confidence_threshold

    def validate(self, results: list[VectorSearchResult]) -> ValidationOutcome:
        confidence = self._confidence_scorer.score(results)
        warnings = self._contradiction_detector.detect(results)

        if confidence < self._confidence_threshold:
            return ValidationOutcome(
                confidence=confidence,
                warnings=warnings,
                should_abstain=True,
                abstain_reason=(
                    f"Confiance insuffisante ({confidence:.2f} < seuil "
                    f"{self._confidence_threshold:.2f}) pour générer une réponse "
                    f"fiable à partir des preuves récupérées."
                ),
            )

        return ValidationOutcome(
            confidence=confidence, warnings=warnings, should_abstain=False, abstain_reason=None
        )
