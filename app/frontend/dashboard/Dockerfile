FROM node:20-alpine
WORKDIR /app
COPY package.json tsconfig.json next.config.js ./
COPY app ./app
RUN npm install
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
