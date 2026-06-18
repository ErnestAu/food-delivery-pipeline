FROM python:3.11-slim
WORKDIR /app
COPY requirements-sim.txt .
RUN pip install --no-cache-dir -r requirements-sim.txt
COPY simulator/ ./simulator/
ENTRYPOINT ["python", "-m", "simulator.main"]