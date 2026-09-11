import argparse, json
from types import SimpleNamespace
from pathlib import Path
from app.modules.evaluation.report import write_report
from app.modules.evaluation.contracts import BenchmarkReport, VariantReport, QuestionEvalResult, PipelineVariant

# Régénère les fichiers à partir du JSON produit par le benchmark.
def main():
    p=argparse.ArgumentParser(); p.add_argument("json"); p.add_argument("--output",default="evaluation_results"); a=p.parse_args()
    raw=json.loads(Path(a.json).read_text(encoding="utf-8"))
    # Le JSON est déjà une représentation de rapport; pour les graphiques, on reconstruit minimalement les dataclasses.
    variants={}
    for key, data in raw.get("variants", raw).items():
        v=PipelineVariant(key)
        results=[]
        for r in data.get("results",[]):
            r=dict(r); r["variant"]=v; r["streaming"]=SimpleNamespace(**r.get("streaming",{})); results.append(QuestionEvalResult(**r))
        d={k:data[k] for k in data if k not in {"variant","results"}}; d["variant"]=v; d["results"]=results; variants[v]=VariantReport(**d)
    write_report(BenchmarkReport(variants),a.output)
if __name__ == "__main__": main()
