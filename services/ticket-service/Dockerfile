
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# We run both the worker (background) and a minimal Flask app to serve PDFs
# For simplicity in this demo, we can just run the worker or use a supervisor.
# Here we will make the main entry point the Flask app, and run the worker in a thread/process.

CMD ["python", "ticket_service.py"]
