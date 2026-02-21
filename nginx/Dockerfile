FROM ubuntu:22.04
RUN apt-get update && apt-get install -y nginx openssl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/key.pem \    
    -out /etc/nginx/ssl/cert.pem \
    -subj "/CN=localhost"
RUN echo '<html><body><h1>Hello from Rom in HTTP!</h1></body></html>' > /var/www/html/index.html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8080 8081 8443
CMD ["nginx", "-g", "daemon off;"]
