FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Fortinet syslog (UDP by default) and, if enabled, TCP.
EXPOSE 5514/udp
EXPOSE 5514/tcp

CMD ["python", "-m", "app.main"]
