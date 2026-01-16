FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY tsconfig.json .
COPY src ./src
COPY lib ./lib
COPY scripts ./scripts
# Copy db schema for initialization
COPY db ./db

RUN npm run build

FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
# Copy lib directory as it might be needed at runtime if not bundled (it's WASM/JS loaded dynamically)
COPY --from=builder /app/lib ./lib
COPY --from=builder /app/db ./db
COPY --from=builder /app/scripts ./scripts

# Install tsx for running scripts
RUN npm install -g tsx

EXPOSE 4000

CMD ["npm", "start"]
