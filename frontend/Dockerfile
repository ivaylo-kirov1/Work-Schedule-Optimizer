# 1) build the React/Vite SPA 
FROM node:22-slim AS build

WORKDIR /app

# install dependencies from the lockfile first 
COPY package.json package-lock.json ./
RUN npm ci


ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY . .
RUN npm run build

# 2) serve static files + reverse-proxy /api to the backend --- nginx-unprivileged runs as non-root (uid 101) on :8080 - no root/setcap needed
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# replace the default server block with our SPA-fallback + /api proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# static assets produced by the build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

