FROM python:3.9-alpine

WORKDIR /two-tier-app

COPY requirements.txt .

# Installer gcc et dépendances pour mysqlclient et installer Python deps
RUN apk add --no-cache gcc musl-dev mariadb-connector-c-dev \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python","-u","app.py"]
