FROM nginx:alpine

RUN rm -rf /usr/share/nginx/html/*

WORKDIR /usr/share/nginx/html

COPY ./nginx.conf /etc/nginx/templates/default.conf.template

COPY ./www .

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]