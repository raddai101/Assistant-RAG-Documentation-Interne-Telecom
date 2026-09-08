# TEKIS — Guide d'installation de l'environnement local (Windows / PowerShell natif)

Ce guide couvre **tout** ce qu'il faut installer pour faire tourner et tester le
**backend TEKIS seul**, en PowerShell natif (pas de WSL, pas de Git Bash), sur Windows
10/11 : Python et ses bibliothèques, PostgreSQL, Neo4j, Ollama (LLM + embeddings), et
le reranker (HuggingFace).

Le frontend (`tekis-frontend/`) n'est **pas** concerné par ce guide et ne doit pas être
démarré ni fusionné avec le backend à ce stade — conformément aux instructions
permanentes du projet (périmètre actuel = backend uniquement).

Vérifié contre le code réel du projet (`requirements.txt`, `config.py`, `.env.example`,
imports dans `app/`) — pas seulement recopié depuis une doc générique.

> **Toutes les commandes ci-dessous s'exécutent dans PowerShell** (pas `cmd.exe`, pas
> Git Bash). Ouvrez PowerShell normalement pour la majorité des étapes ; les rares
> commandes nécessitant les droits administrateur sont explicitement marquées
> **(Admin)**.

---

## 0. Vue d'ensemble — ce qu'il y a à installer

| Composant | Rôle dans TEKIS | Obligatoire ? | Installation Windows |
|---|---|---|---|
| Python 3.11+ | Exécute le backend Flask | Oui | Installeur officiel ou `winget` |
| PostgreSQL 14+ | Base relationnelle + recherche lexicale FTS (Phase 3) | Oui | Installeur officiel EDB |
| Neo4j 5.x | Knowledge Graph (Phase 4) | Oui (dès que `/api/v1/graph` est utilisé) | Docker Desktop (recommandé) ou Neo4j Desktop |
| Ollama | Sert Qwen3-4B (génération) et BGE-M3 (embeddings) en local | Oui (dès Phase 2) | Installeur officiel `.exe` |
| Bibliothèques Python (`requirements.txt`) | Flask, ORM, parsers, ChromaDB, reranker, driver Neo4j, JWT | Oui | `pip` |
| Build Tools C++ (optionnel) | Compilation de secours si une roue précompilée manque pour `torch`/`tokenizers` | Rare, au cas où | Visual Studio Build Tools |

ChromaDB n'a **pas** de serveur séparé à installer : il tourne en mode embarqué
(fichiers locaux dans `./data/chroma`), c'est une bibliothèque Python comme les autres.

**Différences importantes par rapport à un guide Linux/macOS :**
- Pas d'`apt`/`brew`/`systemctl` : chaque composant a son propre installeur Windows ou
  passe par Docker Desktop.
- Pas de heredoc bash (`<<'SQL'`) : les scripts SQL multi-lignes utilisent une
  *here-string* PowerShell (`@" ... "@`) écrite dans un fichier temporaire.
- `curl` en PowerShell est un **alias vers `Invoke-WebRequest`**, dont la syntaxe des
  options diffère de la vraie commande `curl`. Ce guide utilise systématiquement
  **`curl.exe`** (le vrai binaire curl, inclus nativement depuis Windows 10) pour que
  les commandes `-d`, `-X`, `-H` fonctionnent exactement comme documenté par l'API.
- Les variables d'environnement se déclarent avec `$env:NOM = "valeur"`, pas `export`.

---

## 1. Python et outils système

### 1.1 Python 3.11+

Via l'installeur officiel (recommandé — cochez **"Add python.exe to PATH"** pendant
l'installation) : https://www.python.org/downloads/windows/

Ou via `winget` :
```powershell
winget install -e --id Python.Python.3.11
```

Vérifiez la version dans un **nouveau** terminal PowerShell (pour que le PATH soit à
jour) :
```powershell
python --version   # doit afficher 3.11 ou plus (le code utilise `int | None`, syntaxe 3.10+)
```

> Si `python` n'est pas reconnu après installation, fermez et rouvrez PowerShell, ou
> vérifiez que le dossier `Scripts` de Python a bien été ajouté au `PATH` utilisateur.

### 1.2 Git (pour cloner/gérer le dépôt)

```powershell
winget install -e --id Git.Git
```

### 1.3 Build Tools C++ (optionnel, au cas où)

`psycopg2-binary` et la plupart des roues de `torch`/`tokenizers` sont fournies
précompilées pour Windows x86_64 : dans la grande majorité des cas, **rien à
installer ici**. Ce n'est que si `pip install -r requirements.txt` échoue avec une
erreur de compilation (`error: Microsoft Visual C++ 14.0 or greater is required`)
qu'il faut installer :

```powershell
winget install -e --id Microsoft.VisualStudio.2022.BuildTools
```
Puis, lors de l'installation graphique, cocher le composant **"Desktop development
with C++"**.

### 1.4 Rust (uniquement si l'installation de `tokenizers` échoue malgré les Build Tools)

```powershell
winget install -e --id Rustlang.Rustup
```
Puis fermez/rouvrez PowerShell avant de relancer `pip install`.

### 1.5 Autoriser l'exécution des scripts (nécessaire pour activer un venv)

Par défaut, PowerShell bloque l'exécution de scripts `.ps1` (dont le script
d'activation du venv). À faire une seule fois, dans un PowerShell **(Admin)** :
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Répondez `O` (Oui) si demandé. Cette commande n'affecte que votre utilisateur, pas
tout le système.

---

## 2. Placer le projet et créer l'environnement virtuel

```powershell
cd C:\Users\<votre-nom>\projets      # ou l'emplacement de votre choix
# (placez-y le contenu de tekis-backend, séparément de tekis-frontend)
cd tekis-backend

python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

> Votre invite PowerShell doit maintenant afficher `(venv)` au début de la ligne.
> Toutes les commandes des sections suivantes supposent que le venv est activé.

---

## 3. Bibliothèques Python

### 3.1 Installation directe
```powershell
pip install -r requirements.txt
```

Ceci installe (vérifié contre les imports réels du code, pas seulement le fichier) :

| Paquet | Utilisé pour |
|---|---|
| Flask, Flask-SQLAlchemy, Flask-Migrate | Backend, ORM, migrations |
| psycopg2-binary | Driver PostgreSQL (roue précompilée Windows, embarque déjà `libpq`) |
| python-dotenv | Chargement du `.env` |
| marshmallow | Sérialisation (prévue, peu utilisée à ce stade) |
| pypdf, python-docx, openpyxl | Parsing PDF/DOCX/XLSX (Phase 1) |
| pytest, pytest-cov | Tests |
| chromadb | Vector store embarqué (Phase 2) |
| sentence-transformers | Charge le cross-encoder `BAAI/bge-reranker-v2-m3` (Phase 3) — **tire `torch` et `transformers` en dépendances transitives, installation volumineuse (plusieurs Go)** |
| neo4j | Driver Bolt officiel pour Neo4j (Phase 4) |
| PyJWT | Tokens d'authentification (Phase 5) |

**Attention taille/temps** : `sentence-transformers` entraîne l'installation de
`torch` (~2-3 Go). Sur une connexion lente ou un disque presque plein, prévoyez du
temps. Si vous avez une carte GPU NVIDIA et voulez que le reranker l'utilise,
installez la variante CUDA de `torch` **avant** `pip install -r requirements.txt`
(sinon la version CPU par défaut sera installée) :
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu121   # adapter cu121 à votre version CUDA
pip install -r requirements.txt
```

### 3.2 Vérification
```powershell
python -c "import flask, chromadb, sentence_transformers, neo4j, jwt, psycopg2, pypdf, docx, openpyxl; print('OK, tous les imports fonctionnent')"
```

---

## 4. PostgreSQL

TEKIS utilise PostgreSQL pour les données relationnelles **et** pour la recherche
lexicale (Phase 3, `to_tsvector`/`websearch_to_tsquery` — nécessite **PostgreSQL 11+**,
recommandé 14+).

### 4.1 Installation

Téléchargez l'installeur officiel EDB (inclut `psql`, `pgAdmin`, et le service
Windows) : https://www.postgresql.org/download/windows/

Pendant l'installation :
- notez le **mot de passe du superutilisateur `postgres`** que vous définissez ;
- laissez le port par défaut `5432` ;
- décochez Stack Builder à la fin si vous n'en avez pas besoin.

Vérifiez que `psql` est accessible (un **nouveau** terminal peut être nécessaire) :
```powershell
psql --version
```
Si `psql` n'est pas reconnu, ajoutez manuellement au PATH (adapter la version) :
```powershell
$env:Path += ";C:\Program Files\PostgreSQL\18\bin"
```

### 4.2 Créer l'utilisateur et les bases de données

Le projet attend deux bases : `tekis_db` (application) et `tekis_test` (utilisée par
les tests d'intégration réels PostgreSQL, `tests/integration/*_real_postgres.py`).

Plutôt qu'un heredoc bash (non supporté nativement par `psql.exe` en PowerShell), on
écrit le script SQL dans un fichier temporaire via une *here-string* PowerShell, puis
on l'exécute :

```powershell
@"
CREATE USER tekis_user WITH PASSWORD 'tekis_pass';
CREATE DATABASE tekis_db OWNER tekis_user;
CREATE DATABASE tekis_test OWNER tekis_user;
GRANT ALL PRIVILEGES ON DATABASE tekis_db TO tekis_user;
GRANT ALL PRIVILEGES ON DATABASE tekis_test TO tekis_user;
"@ | Out-File -Encoding utf8 -FilePath "$env:TEMP\tekis_init.sql"

psql -U postgres -h localhost -f "$env:TEMP\tekis_init.sql"
```
`psql` vous demandera le mot de passe du superutilisateur `postgres` défini pendant
l'installation.

> Remplacez `tekis_pass` par un mot de passe fort en production — la valeur ci-dessus
> correspond au défaut de `config.py`/`.env.example` pour rester cohérent avec les
> tests fournis.

### 4.3 Vérification
```powershell
psql "postgresql://tekis_user:tekis_pass@localhost:5432/tekis_db" -c "SELECT version();"
```
Doit afficher la version de PostgreSQL sans erreur d'authentification.

### 4.4 Créer les tables (le projet n'a pas encore de migration Alembic initialisée)
```powershell
$env:FLASK_APP = "run.py"
flask db init          # une seule fois, crée le dossier migrations/
flask db migrate -m "Schéma initial TEKIS"
flask db upgrade
```
Alternative rapide (sans Alembic, moins adaptée à la production mais suffisante pour
tester) :
```powershell
python -c "from app import create_app; from app.extensions import db; app = create_app('development'); app.app_context().push(); db.create_all(); print('Tables créées')"
```

---

## 5. Neo4j (Knowledge Graph, Phase 4)

### 5.1 Installation — option recommandée : Docker Desktop

C'est l'option la plus simple et la plus fiable sous Windows, et elle correspond
exactement à l'option "Docker" déjà envisagée dans la version Linux/macOS du guide.

1. Installez Docker Desktop : https://www.docker.com/products/docker-desktop/
   (ou `winget install -e --id Docker.DockerDesktop`), puis démarrez-le.
2. Lancez le conteneur Neo4j :
```powershell
docker run -d --name tekis-neo4j `
  -p 7474:7474 -p 7687:7687 `
  -e NEO4J_AUTH=neo4j/change-me `
  neo4j:5
```
(la commande `docker run` est strictement identique à celle du guide Linux — Docker
Desktop expose la même CLI sous Windows ; le backtick `` ` `` est le caractère de
continuation de ligne en PowerShell, équivalent au `\` bash.)

### 5.2 Installation — option alternative : Neo4j Desktop natif

Si vous ne voulez pas de Docker : https://neo4j.com/download/ → **Neo4j Desktop**.
Créez une base locale, démarrez-la, puis notez le port Bolt (`7687` par défaut).
Ajoutez `cypher-shell.bat` (fourni avec l'installation) à votre PATH si vous voulez
l'utiliser en ligne de commande.

### 5.3 Définir/vérifier le mot de passe

Avec Docker, `NEO4J_AUTH=neo4j/change-me` a déjà défini le mot de passe à la création
du conteneur — rien à faire de plus. Pour vérifier :
```powershell
docker exec -it tekis-neo4j cypher-shell -u neo4j -p change-me "RETURN 1 AS ok;"
```

Avec Neo4j Desktop natif, le mot de passe est défini lors de la création de la base
dans l'interface graphique ; utilisez ensuite :
```powershell
cypher-shell -u neo4j -p change-me "RETURN 1 AS ok;"
```

Mettez à jour votre `.env` en conséquence (`NEO4J_PASSWORD=change-me`).

Interface web (facultative, pratique pour visualiser le graphe) :
`http://localhost:7474`

---

## 6. Ollama (Qwen3-4B + BGE-M3, exécution locale)

### 6.1 Installation

Téléchargez et lancez l'installeur Windows officiel :
https://ollama.com/download/windows

Après installation, Ollama tourne automatiquement en arrière-plan (icône dans la
zone de notification) — il n'y a **pas** besoin de lancer `ollama serve` séparément
comme sous Linux, sauf si vous l'avez explicitement arrêté.

### 6.2 Télécharger les modèles utilisés par TEKIS
```powershell
ollama pull qwen3:4b
ollama pull bge-m3
```
Ces noms doivent correspondre exactement à `OLLAMA_LLM_MODEL` et
`OLLAMA_EMBEDDING_MODEL` dans votre `.env`.

### 6.3 Vérification directe (sans passer par TEKIS)
```powershell
# Génération
$body = @{
    model  = "qwen3:14b"
    prompt = "Réponds uniquement par OK."
    stream = $false
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:11434/api/generate" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response

# Embedding
$body = @{
    model = "bge-m3"
    input = "Ceci est un document de test pour TEKIS."
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:11434/api/embed" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response
```
Le premier appel doit renvoyer un champ `"response"`, le second un champ
`"embedding"` (liste de nombres) — **ce sont exactement les champs que
`OllamaLLMClient`/`OllamaEmbeddingClient` attendent** (`app/modules/generation/
ollama_client.py`). Si la forme diffère, le code lèvera une `OllamaError` explicite.

> Notez le `.exe` explicite après `curl` : sans lui, PowerShell utilise son alias
> `Invoke-WebRequest`, qui interprète `-d` différemment et cassera cette commande.

---

## 7. Reranker (`BAAI/bge-reranker-v2-m3`, Phase 3)

Contrairement à Ollama, ce modèle n'est **pas** servi par Ollama : il est chargé
directement en mémoire par `sentence-transformers` (Hugging Face), au premier appel
réel du reranker (chargement paresseux, voir
`app/modules/retrieval/reranker/cross_encoder.py`).

### 7.1 Rien à "installer" séparément
Le modèle (~1,1 Go) se télécharge automatiquement depuis Hugging Face Hub au premier
usage, et est mis en cache localement (`%USERPROFILE%\.cache\huggingface\`).
Assurez-vous simplement d'avoir un accès réseau à `huggingface.co` la première fois.

### 7.2 Pré-télécharger le modèle manuellement (optionnel, utile pour éviter un délai au premier appel API)
```powershell
python -c "from sentence_transformers import CrossEncoder; model = CrossEncoder('BAAI/bge-reranker-v2-m3'); print('Reranker chargé, prêt.')"
```

### 7.3 Vérification fonctionnelle
Pour un script Python multi-lignes, le plus simple en PowerShell natif est d'utiliser
une *here-string* passée sur l'entrée standard de `python -` :
```powershell
@'
from sentence_transformers import CrossEncoder
model = CrossEncoder("BAAI/bge-reranker-v2-m3")
scores = model.predict([
    ("procédure SGSN", "La procédure SGSN décrit la maintenance réseau."),
    ("procédure SGSN", "Recette de cuisine pour un gâteau au chocolat."),
])
print(scores)  # le score du premier couple doit être nettement plus élevé
'@ | python -
```

---

## 8. Fichier `.env`

```powershell
Copy-Item .env.example .env
```
Éditez `.env` (avec le Bloc-notes, VS Code, etc.) pour faire correspondre les mots de
passe choisis aux sections 4.2 et 5.3 ci-dessus (`DATABASE_URL`, `NEO4J_PASSWORD`).
Générez des secrets forts pour la production :
```powershell
python -c "import secrets; print(secrets.token_hex(32))"   # à utiliser pour SECRET_KEY et JWT_SECRET_KEY
```

---

## 9. Lancer l'application

```powershell
$env:FLASK_APP = "run.py"
$env:FLASK_ENV = "development"
flask run
# ou directement :
python run.py
```
Test rapide (dans un **autre** terminal PowerShell, celui qui fait tourner Flask
restant occupé) :
```powershell
curl.exe http://localhost:5000/api/v1/health
# Attendu : {"success": true, "data": {"status": "ok"}, ...}
```

---

## 10. Lancer les tests

### 10.1 Suite complète (SQLite en mémoire, pas besoin de Postgres/Neo4j/Ollama)
```powershell
$env:FLASK_ENV = "testing"
$env:SECRET_KEY = "test"
$env:JWT_SECRET_KEY = "test"
pytest tests/ -v
```
La grande majorité des tests (Ollama, reranker, Neo4j mockés) tournent ainsi sans
aucune infrastructure externe.

### 10.2 Tests nécessitant un vrai PostgreSQL
Ces deux fichiers ciblent spécifiquement `tekis_test` (créée en §4.2) :
```powershell
pytest tests/integration/test_hybrid_retrieval_real_postgres.py -v
pytest tests/integration/test_change_intelligence_real_postgres.py -v
```
S'ils échouent à la connexion, vérifiez
`postgresql://tekis_user:tekis_pass@localhost:5432/tekis_test` (identifiants en dur
dans ces fichiers de test, à adapter si vous avez changé le mot de passe).

### 10.3 Tout lancer d'un coup
```powershell
pytest tests/ -v
```

---

## 11. Test de bout en bout manuel (avec toute l'infrastructure démarrée)

```powershell
# 1. Connexion (remplacez par un utilisateur existant en base, ou créez-en un via un script)
$response = curl.exe -s -X POST http://localhost:5000/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d '{"email": "nkashamaradda.arc@gmail.com", "password": "chat@tekis"}'
$TOKEN = $response | python -c "import sys, json; print(json.load(sys.stdin)['data']['access_token'])"

# 2. Ingestion d'un document
curl.exe -X POST http://localhost:5000/api/v1/ingestion `
  -F "title=Test procédure" `
  -F "file=@C:\Users\Academy\Documents\tekis\corpus\enterprise\Cybersecurite Telecom\DOC09_Cybersecurite_Projet_Bouclier.docx"

# 3. Indexation vectorielle (BGE-M3 via Ollama)
curl.exe -X POST http://localhost:5000/api/v1/embeddings/reindex -H "Content-Type: application/json" -d '{}'

# 4. Recherche (nécessite le token)
curl.exe -X POST http://localhost:5000/api/v1/search `
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" `
  -d '{"query": "procédure", "top_k": 5}'

# 5. Question-réponse complète (Ollama + reranker + validation)
curl.exe -X POST http://localhost:5000/api/v1/chat `
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" `
  -d '{"query": "Que dit le document sur la procédure ?"}'
```
Un utilisateur admin n'existe pas encore par défaut — créez-en un via un script
Python (`werkzeug.security.generate_password_hash` + insertion `User`/`Role`), à
adapter selon vos besoins ; ce point n'est pas encore couvert par une route API dédiée
(aucun `POST /api/v1/users` n'existe à ce stade du projet).

---

## 12. Récapitulatif — checklist avant de dire "tout fonctionne"

- [ ] `python --version` ≥ 3.11
- [ ] `.\venv\Scripts\Activate.ps1` active bien `(venv)` dans l'invite
- [ ] `pip install -r requirements.txt` termine sans erreur
- [ ] `psql ... -c "SELECT version();"` répond (PostgreSQL ≥ 11)
- [ ] `docker exec -it tekis-neo4j cypher-shell ... "RETURN 1;"` (ou `cypher-shell` natif) répond (Neo4j)
- [ ] `ollama list` affiche `qwen3:4b` et `bge-m3`
- [ ] `curl.exe http://localhost:11434/api/generate ...` renvoie un `response`
- [ ] `curl.exe http://localhost:11434/api/embeddings ...` renvoie un `embedding`
- [ ] Le reranker se charge sans erreur (§7.2)
- [ ] `flask db upgrade` (ou `db.create_all()`) a créé les tables
- [ ] `curl.exe http://localhost:5000/api/v1/health` répond `{"status": "ok"}`
- [ ] `pytest tests/ -v` : tous verts
- [ ] `pytest tests/integration/*_real_postgres.py -v` : tous verts
- [ ] `tekis-frontend/` n'a pas été démarré ni référencé — backend testé isolément
