# Production build of the web UI, served by nginx. Built by `docker compose --profile web up -d web`.
FROM node:22.23.5-alpine3.23 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.29.8-alpine3.23
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
# MANIFEST.md and score_table.md are mounted read-only at /evidence by docker-compose.yml.
EXPOSE 8080
