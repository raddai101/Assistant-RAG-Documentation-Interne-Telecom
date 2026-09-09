"""
Configuration de l'application TEKIS, séparée du code (règle §11 des instructions
permanentes du projet). Toute valeur sensible provient des variables d'environnement,
jamais codée en dur.
"""
import os


class BaseConfig:
    """Configuration commune à tous les environnements."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://tekis_user:tekis_pass@localhost:5432/tekis_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES_MINUTES = int(
        os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "60")
    )
    # Rôle(s) bénéficiant d'un accès illimité au corpus (bypass ACL, memoire.md §27) —
    # séparés par des virgules dans la variable d'environnement. Politique à
    # confirmer par Radda101, voir AccessControlService.
    ADMIN_ROLE_NAMES = frozenset(
        r.strip() for r in os.environ.get("ADMIN_ROLE_NAMES", "admin").split(",") if r.strip()
    )

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_LLM_MODEL = os.environ.get("OLLAMA_LLM_MODEL", "qwen3:14b")
    OLLAMA_EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "bge-m3")
    OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.15"))
    OLLAMA_TOP_P = float(os.environ.get("OLLAMA_TOP_P", "0.9"))
    OLLAMA_TOP_K = int(os.environ.get("OLLAMA_TOP_K", "10"))

    CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma")
    CHROMA_COLLECTION_NAME = os.environ.get(
        "CHROMA_COLLECTION_NAME", "tekis_enterprise_kb"
    )
    RETRIEVAL_TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", "5"))
    RERANKER_MODEL_NAME = os.environ.get("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
    HYBRID_CANDIDATE_K = int(os.environ.get("HYBRID_CANDIDATE_K", "20"))
    # Seuil de confiance sous lequel GenerationService s'abstient plutôt que de
    # générer une réponse (Phase 6, memoire.md §29). Première estimation non
    # calibrée, faute d'accès à un reranker réel dans l'environnement de
    # développement — à ajuster par Radda101 une fois le reranker en service.
    CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.5"))

    NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "change-me")

    MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50"))
    INGESTION_STORAGE_DIR = os.environ.get(
        "INGESTION_STORAGE_DIR", "./data/documents"
    )
    QUARANTINE_DIR = os.environ.get("QUARANTINE_DIR", "./data/quarantine")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )


class ProductionConfig(BaseConfig):
    DEBUG = False


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
