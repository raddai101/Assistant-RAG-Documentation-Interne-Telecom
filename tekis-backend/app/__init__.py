"""
App factory Flask pour TEKIS.

Respecte la séparation architecturale imposée (§9 des instructions permanentes) :
les blueprints dans `app/api/` ne contiennent que des routes HTTP, la logique métier
vit dans `app/modules/<nom>/service.py`, l'accès aux données dans les repositories.
"""
import os

from flask import Flask, request
from dotenv import load_dotenv

from app.extensions import db, migrate
from config import CONFIG_BY_NAME

def create_app(config_name: str | None = None, config_overrides: dict | None = None) -> Flask:
    load_dotenv()

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(CONFIG_BY_NAME[config_name])
    if config_overrides:
        # Appliqué AVANT db.init_app() : Flask-SQLAlchemy crée le moteur dès
        # l'initialisation de l'extension (pas paresseusement au premier accès),
        # donc modifier app.config après coup n'a aucun effet sur SQLALCHEMY_DATABASE_URI.
        # Utilisé par les tests qui doivent pointer vers un vrai PostgreSQL (ex.
        # Full-Text Search, non disponible sur le SQLite de TestingConfig).
        app.config.update(config_overrides)
    # Application matérielle de la limite de taille au niveau WSGI (Werkzeug renvoie
    # 413 automatiquement) — en plus du contrôle applicatif fait par FileValidator,
    # qui vérifie la taille réelle du fichier une fois reçu (défense en profondeur).
    app.config["MAX_CONTENT_LENGTH"] = app.config["MAX_UPLOAD_SIZE_MB"] * 1024 * 1024

    @app.after_request
    def add_local_cors_headers(response):
        origin = request.headers.get("Origin", "")
        allowed_origins = {
            "null",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        }
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    db.init_app(app)
    migrate.init_app(app, db)

    # Modèles importés ici (pas au niveau module) pour éviter les imports circulaires
    # avec `db`, tout en garantissant qu'ils sont enregistrés avant les migrations.
    with app.app_context():
        from app import models  # noqa: F401

    _register_blueprints(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from app.api.health import health_bp
    from app.api.ingestion import ingestion_bp
    from app.api.documents import documents_bp
    from app.api.embeddings import embeddings_bp
    from app.api.search import search_bp
    from app.api.chat import chat_bp
    from app.api.conversations import conversations_bp
    from app.api.graph import graph_bp
    from app.api.auth import auth_bp
    from app.api.change_intelligence import change_intelligence_bp
    from app.api.evaluation import evaluation_bp
    from app.api.administration import administration_bp

    app.register_blueprint(health_bp, url_prefix="/api/v1/health")
    app.register_blueprint(ingestion_bp, url_prefix="/api/v1/ingestion")
    app.register_blueprint(documents_bp, url_prefix="/api/v1/documents")
    app.register_blueprint(embeddings_bp, url_prefix="/api/v1/embeddings")
    app.register_blueprint(search_bp, url_prefix="/api/v1/search")
    app.register_blueprint(chat_bp, url_prefix="/api/v1/chat")
    app.register_blueprint(conversations_bp, url_prefix="/api/v1/conversations")
    app.register_blueprint(graph_bp, url_prefix="/api/v1/graph")
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(change_intelligence_bp, url_prefix="/api/v1/change-intelligence")
    app.register_blueprint(evaluation_bp, url_prefix="/api/v1/evaluation")
    app.register_blueprint(administration_bp, url_prefix="/api/v1/admin")
