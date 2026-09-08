from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="GSMA/oran",
    repo_type="dataset",
    local_dir="./data/oran",
    allow_patterns="original/**"
)

print(path)
FeB4RAG Evaluating Federated Search in the Context of Retrieval
Augmented Generation
