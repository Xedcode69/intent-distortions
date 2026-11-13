FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY demo/nginx.conf /etc/nginx/conf.d/default.conf
COPY demo/index.html demo/styles.css demo/app.mjs demo/core.mjs /usr/share/nginx/html/
COPY demo/assets /usr/share/nginx/html/assets
EXPOSE 8080
