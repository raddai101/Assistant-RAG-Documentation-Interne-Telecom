"""
Extensions Flask instanciées une seule fois et attachées à l'app dans la factory
(app/__init__.py). Évite les imports circulaires entre modules/models.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
