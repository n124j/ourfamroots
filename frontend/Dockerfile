# ── Stage 1: Node builder ────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build

# Install deps first (layer cache)
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Copy source and build
COPY . .

ARG VITE_API_BASE_URL=/api/v1
ARG GOOGLE_CLIENT_ID=
ARG GITHUB_CLIENT_ID=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
ENV GITHUB_CLIENT_ID=$GITHUB_CLIENT_ID

RUN npm run build


# ── Stage 2: Nginx serving ───────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

LABEL org.opencontainers.image.description="OurFamRoots Frontend"

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /build/dist /usr/share/nginx/html

# Non-root nginx: bind to 8080
RUN chown -R nginx:nginx /var/cache/nginx /var/run \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
