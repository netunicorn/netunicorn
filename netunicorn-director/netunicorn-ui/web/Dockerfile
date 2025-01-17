# Stage 1: Build React App
FROM node:16-alpine as build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

RUN mv /app/build/index.html /app/build/index.html.template

# Stage 2: Serve with Nginx + envsubst

FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html

CMD ["sh", "-c", "envsubst < /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html && nginx -g 'daemon off;'"]

COPY nginx.conf /etc/nginx/conf.d/default.conf
