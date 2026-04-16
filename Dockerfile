FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/received_photos

COPY . .

ENTRYPOINT ["python", "src/calibrator_runner.py"]