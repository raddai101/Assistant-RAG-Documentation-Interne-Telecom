FROM python:3.12-slim

# ============================================================
# Configuration Python
# ============================================================

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


# ============================================================
# Dépendances système
# ============================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*


# ============================================================
# Installation des dépendances Python
# ============================================================

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn psycopg2-binary


# ============================================================
# Copie du backend
# ============================================================

COPY . .


# ============================================================
# Création des répertoires persistants
# ============================================================

RUN mkdir -p \
    /app/data/chroma \
    /app/data/documents \
    /app/data/quarantine


# ============================================================
# Port Flask/Gunicorn
# ============================================================

EXPOSE 5000


# ============================================================
# Démarrage
# ============================================================

CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 300 run:app"]