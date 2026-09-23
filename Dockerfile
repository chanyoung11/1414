# 1414 운영 이미지 (Google Cloud Run)
FROM node:24-slim
ENV NODE_ENV=production
WORKDIR /srv
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force
COPY server.mjs ./
COPY api ./api
COPY lib ./lib
COPY app ./app
USER node
CMD ["node", "server.mjs"]
