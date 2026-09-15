FROM node:26-alpine@sha256:ef24c5053d50fdc3e4e56eb4e7ddb7861874ab0fdc797046ba897581deb8e868 AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:26-alpine@sha256:ef24c5053d50fdc3e4e56eb4e7ddb7861874ab0fdc797046ba897581deb8e868 AS builder
WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=768
ARG NEXT_PUBLIC_TELEGRAM_BOT_USERNAME
ENV NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=$NEXT_PUBLIC_TELEGRAM_BOT_USERNAME
ARG NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME
ENV NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME=$NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME
# next.config.ts resolves the /api/* rewrite destinations while the build
# runs, so the backend address must be known here. Without it the image
# bakes http://127.0.0.1:8000, which is nothing on the VPS.
ARG API_INTERNAL_URL
ENV API_INTERNAL_URL=$API_INTERNAL_URL
# The public origin is baked into the media remote pattern and the character
# image check, so it must be present at build time -- setting it only in the
# container environment has no effect.
ARG NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:26-alpine@sha256:ef24c5053d50fdc3e4e56eb4e7ddb7861874ab0fdc797046ba897581deb8e868 AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --chown=node:node --from=builder /app/public ./public
COPY --chown=node:node --from=builder /app/.next/standalone ./
COPY --chown=node:node --from=builder /app/.next/static ./.next/static
# Next's standalone tracer sees the musl sharp binding but misses the
# dynamically loaded libvips package. Without it the production image
# silently falls back to serving full-size originals from /_next/image.
COPY --from=deps /app/node_modules/@img/sharp-libvips-linuxmusl-x64 ./node_modules/@img/sharp-libvips-linuxmusl-x64
RUN mkdir -p /app/.next/cache/images && chown -R node:node /app/.next/cache
USER node
EXPOSE 3000
CMD ["node", "server.js"]
