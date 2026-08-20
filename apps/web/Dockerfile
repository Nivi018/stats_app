# Imagen de la web (Next.js). Contexto de build: raíz del repo.
# Construye y sirve el bundle; STATS_API_URL apunta al API en el despliegue.
# Uso: docker build -f apps/web/Dockerfile --build-arg STATS_API_URL=http://api:8000 -t stats-web:<commit> .
FROM node:22-alpine AS builder

WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci

COPY apps/web apps/web
COPY packages packages
RUN npm run build -w @stats/web

FROM node:22-alpine AS runtime

ARG STATS_API_URL=http://api:8000
ENV NODE_ENV=production \
    STATS_API_URL=${STATS_API_URL}

WORKDIR /repo
RUN addgroup -S app && adduser -S app -G app

COPY --from=builder --chown=app:app /repo/node_modules ./node_modules
COPY --from=builder --chown=app:app /repo/apps/web/.next ./apps/web/.next
COPY --from=builder --chown=app:app /repo/apps/web/public ./apps/web/public
COPY --from=builder --chown=app:app /repo/apps/web/package.json ./apps/web/package.json
COPY --from=builder --chown=app:app /repo/apps/web/next.config.ts ./apps/web/next.config.ts
COPY --from=builder --chown=app:app /repo/apps/web/tsconfig.json ./apps/web/tsconfig.json
COPY --from=builder --chown=app:app /repo/apps/web/next-env.d.ts ./apps/web/next-env.d.ts

USER app
EXPOSE 3000

CMD ["npm", "run", "start", "-w", "@stats/web"]
