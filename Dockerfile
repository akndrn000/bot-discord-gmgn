FROM python:3.10-slim

WORKDIR /app

# Install git untuk menginstal paket discord.py-self dari repo Github
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
