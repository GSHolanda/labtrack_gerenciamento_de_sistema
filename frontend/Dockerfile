# syntax=docker/dockerfile:1
# Interface do LabTrack: build do Vite com Node e arquivos estáticos servidos pelo
# Nginx, que também encaminha /api para a API (mesma origem, sem CORS).

# --- build ------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# true: a tela de login lista os usuários de demonstração.
ARG VITE_DEMO_MODE=false
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE
RUN npm run build

# --- runtime ----------------------------------------------------------------------
FROM nginx:1.28-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1
