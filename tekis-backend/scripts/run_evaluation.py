import argparse
from app.modules.evaluation.dataset import load_dataset
from app.modules.evaluation.config import BenchmarkConfig
from app.modules.evaluation.runner import EvaluationRunner
from app.modules.evaluation.report import write_report
from app.modules.evaluation.contracts import PipelineVariant


def main():
    p=argparse.ArgumentParser(); p.add_argument("--dataset",required=True); p.add_argument("--output",default="evaluation_results"); p.add_argument("--parallel",type=int,default=4); p.add_argument("--no-streaming",action="store_true")
    args=p.parse_args()
    # Le script est destiné à être lancé dans un contexte Flask applicatif.
    from run import app
    with app.app_context():
        questions=load_dataset(args.dataset)
        from app.api.evaluation import _build_runners
        runners=_build_runners(app.config)
        runner=EvaluationRunner(runners, max_workers=args.parallel, streaming=not args.no_streaming)
        report=runner.run_report(questions, {"variants":[v.value for v in PipelineVariant],"parallel":args.parallel})
        write_report(report,args.output)
        print(f"Benchmark terminé: {args.output}")

if __name__ == "__main__": main()
