FROM python:3.11-slim
WORKDIR /app
RUN pip install requests
COPY test_nginx.py .
CMD ["python", "test_nginx.py"]