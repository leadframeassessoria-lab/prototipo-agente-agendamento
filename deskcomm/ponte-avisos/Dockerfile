# Ponte de avisos Leadframe — imagem pequena, usuário sem privilégio, estado em /data.
FROM node:22-alpine

ENV NODE_ENV=production \
    PONTE_DIR_ESTADO=/data

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY src ./src
COPY scripts ./scripts
COPY teste/fixtures ./teste/fixtures

RUN mkdir -p /data && chown node:node /data
USER node
VOLUME ["/data"]

HEALTHCHECK --interval=60s --timeout=5s --start-period=90s --retries=3 \
  CMD ["node", "src/saude.mjs"]

CMD ["node", "src/principal.mjs"]
