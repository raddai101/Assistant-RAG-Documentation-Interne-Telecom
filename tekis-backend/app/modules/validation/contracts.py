"""
Contrats du module `validation` (Phase 6, memoire.md §14). Pas de Protocol ici :
`ConfidenceScorer` et `ContradictionDetector` sont de la logique pure, injectée par
composition dans `ValidationService` — un contrat formel n'apporterait rien de plus
que la signature des méthodes elles-mêmes.
"""
from dataclasses import dataclass, field


@dataclass
class ValidationOutcome:
    confidence: float
    warnings: list[str] = field(default_factory=list)
    should_abstain: bool = False
    abstain_reason: str | None = None
