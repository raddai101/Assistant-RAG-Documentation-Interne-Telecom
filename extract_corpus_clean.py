from pathlib import Path

src = Path("tekis_db.sql")
dst = Path("tekis_corpus_data_only_clean.sql")

tables = [
    b"documents",
    b"document_versions",
    b"chunks",
    b"chunk_embeddings",
    b"permissions",
]

data = src.read_bytes()

# Normalisation uniquement des fins de lignes.
# Les octets UTF-8 du contenu restent inchangés.
data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

blocks = []

for table in tables:
    header = b"COPY public." + table + b" "
    start = data.find(header)

    if start == -1:
        raise RuntimeError(
            f"Bloc COPY introuvable pour {table.decode()}"
        )

    end = data.find(b"\n\\.\n", start)

    if end == -1:
        raise RuntimeError(
            f"Fin de COPY introuvable pour {table.decode()}"
        )

    end += len(b"\n\\.\n")

    blocks.append(data[start:end])

result = b"\n".join(blocks)

dst.write_bytes(result)

print(f"Fichier créé : {dst}")
print(f"Taille : {len(result):,} octets")
print()

for table, block in zip(tables, blocks):
    print(
        f"{table.decode():20s} : "
        f"{block.count(b'\\n'):,} lignes/octet-lignes"
    )

print()
print("Blocs extraits :", len(blocks))
