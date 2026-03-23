FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*
RUN pip install requests
COPY test_nginx.py .
CMD ["python", "test_nginx.py"]