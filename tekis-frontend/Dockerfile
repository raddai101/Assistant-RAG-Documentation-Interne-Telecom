FROM nginx:alpine

# Supprime la configuration Nginx par défaut
RUN rm -f /etc/nginx/conf.d/default.conf

# Configuration TEKIS
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Frontend
COPY . /usr/share/nginx/html

EXPOSE 80