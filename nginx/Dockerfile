FROM ubuntu:22.04
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8080 8081
CMD ["nginx", "-g", "daemon off;"]