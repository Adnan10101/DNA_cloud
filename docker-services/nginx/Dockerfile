FROM nginx:alpine

RUN apk add --no-cache \    
    curl \  
    bash \  
    nano \  
    openssl

RUN mkdir -p /etc/nginx/conf.d \
             /etc/nginx/ssl \
             /etc/nginx/snippets \
             /var/log/nginx

COPY nginx.conf /etc/nginx/nginx.conf

CMD ["nginx", "-g", "daemon off;"]