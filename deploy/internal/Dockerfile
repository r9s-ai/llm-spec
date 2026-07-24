FROM node:24-bookworm-slim

ARG SOURCE_REPOSITORY=https://github.com/r9s-ai/llm-spec
ARG SOURCE_REVISION=unknown

LABEL org.opencontainers.image.source="${SOURCE_REPOSITORY}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      com.r9s.deploy.managed="true" \
      com.r9s.deploy.service="r9s-llm-spec"

RUN npm install --global pnpm@9.15.1 \
    && npm cache clean --force

WORKDIR /app
COPY source/ /app/
RUN pnpm install --frozen-lockfile \
    && pnpm build:service \
    && mkdir -p /var/lib/llm-spec/history \
    && chown -R node:node /app /var/lib/llm-spec/history \
    && pnpm store prune

ENV NODE_ENV=production \
    LLM_SPEC_BACKEND_HOST=0.0.0.0 \
    LLM_SPEC_BACKEND_PORT=8788 \
    LLM_SPEC_HISTORY_DIR=/var/lib/llm-spec/history \
    LLM_SPEC_REVISION=unknown

USER node
EXPOSE 8788

HEALTHCHECK --interval=5s --timeout=5s --start-period=30s --retries=60 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:' + (process.env.LLM_SPEC_BACKEND_PORT || '8788') + '/api/health').then((response) => { if (!response.ok) process.exit(1); }).catch(() => process.exit(1));"]

CMD ["node", "packages/llm-spec/dist/server.js"]
