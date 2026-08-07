FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
# VITE_* values are inlined at build time, so the API URL has to be known here
# rather than at container start. This is the URL the *browser* uses.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Vite emits plain static files, so the runtime image is just a web server —
# a few MB rather than a Node process.
FROM nginx:1.27-alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
