"""Exports JSON/CSV et graphiques du benchmark."""
import csv, json
from pathlib import Path


def _primitive(obj):
    if hasattr(obj, "value"): return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _primitive(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, dict): return {str(k): _primitive(v) for k,v in obj.items()}
    if isinstance(obj, (list, tuple)): return [_primitive(x) for x in obj]
    return obj


def write_report(report, output_dir: str | Path):
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    payload = _primitive(report)
    (out / "raw_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for variant, vr in report.variants.items():
        d = _primitive(vr); d.pop("results", None); rows.append(d)
    fields = sorted({k for r in rows for k in r})
    with open(out / "variant_summary.csv", "w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    qrows=[]
    for vr in report.variants.values():
        for r in vr.results: qrows.append(_primitive(r))
    if qrows:
        fields=sorted({k for r in qrows for k in r})
        with open(out / "question_results.csv", "w", newline="", encoding="utf-8") as f:
            w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(qrows)
    _graphs(report, out)
    return out


def _graphs(report, out):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    variants=list(report.variants.values()); labels=[v.variant.value.split("_",1)[0] for v in variants]
    charts=[
        ("retrieval_comparison.png", "Retrieval A→G", ["mean_recall_at_k","mean_reciprocal_rank","mean_ndcg_at_k"]),
        ("generation_comparison.png", "Génération A→G", ["mean_faithfulness","mean_answer_relevance"]),
        ("citation_comparison.png", "Citations A→G", ["mean_citation_precision","mean_citation_recall","mean_citation_completeness"]),
        ("version_comparison.png", "Versions A→G", ["mean_version_accuracy","mean_version_completeness"]),
        ("latency_comparison.png", "Latence A→G", ["mean_latency_ms"]),
        ("streaming_comparison.png", "Streaming A→G", ["mean_ttft_ms","mean_tokens_per_second"]),
    ]
    for filename,title,attrs in charts:
        fig, ax = plt.subplots(figsize=(10,5)); x=range(len(labels)); width=0.8/max(1,len(attrs))
        for i,a in enumerate(attrs):
            vals=[getattr(v,a) if getattr(v,a) is not None else 0 for v in variants]
            ax.bar([p+(i-len(attrs)/2+0.5)*width for p in x], vals, width, label=a.replace("mean_", ""))
        ax.set_title(title); ax.set_xticks(list(x), labels); ax.legend(); ax.grid(axis="y", alpha=.25)
        fig.tight_layout(); fig.savefig(out/filename, dpi=160); plt.close(fig)
