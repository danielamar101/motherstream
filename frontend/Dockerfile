# Stage 0, "build-stage", based on Node.js, to build and compile the frontend
FROM node:20 AS build-stage

WORKDIR /app/

COPY package*.json /app/

RUN npm install

COPY . /app

# Build argument for API URL (optional, can be overridden at runtime in dev mode)
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

# Build the frontend (for production)
RUN npm run build-only

# Development mode - runs vite dev server
# Environment variables will be loaded at runtime from k8s secrets
CMD ["npm", "run", "dev"]