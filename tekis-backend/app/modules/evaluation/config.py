from dataclasses import dataclass, field
from .contracts import PipelineVariant

@dataclass(frozen=True)
class BenchmarkConfig:
    variants: tuple[PipelineVariant, ...] = tuple(PipelineVariant)
    top_k: int = 5
    max_workers: int = 4
    streaming: bool = True
    output_dir: str = "evaluation_results"
    metadata: dict = field(default_factory=dict)
