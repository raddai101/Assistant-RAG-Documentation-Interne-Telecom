import argparse
from app.modules.evaluation.dataset import load_dataset
p=argparse.ArgumentParser(); p.add_argument("dataset"); args=p.parse_args(); qs=load_dataset(args.dataset); print(f"Dataset valide: {len(qs)} questions")
