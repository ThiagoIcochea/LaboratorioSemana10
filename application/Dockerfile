FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
# 1 proceso con hilos: las métricas del cliente Prometheus quedan en un único registro
CMD ["gunicorn", "-w", "1", "--threads", "32", "-b", "0.0.0.0:8000", "--timeout", "30", "app:app"]
