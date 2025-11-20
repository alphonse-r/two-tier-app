
# Description du projet

Ce projet est une application web minimale développée avec Flask et connectée à une base de données MariaDB sur une instance EC2 d'AWS.

L’application expose trois routes :

`*/` -> Route principale 

`*/mysql` -> Vérifie la connexion à MariaDB

`*/health` -> Vérifie l'état de santé de l'app (utile pour Docker, docker-compose)

L’objectif est également d’apprendre à containeriser, déployer et orchestrer une application complète en utilisant Docker (Dockerfile) et docker-compose.

Le projet inclut également un pipeline CI/CD avec Jenkins qui est déclenché automatiquement via Webhook GitHub.

# Etape 1: Préparation de l'instance EC2

### Créer l'instance EC2 :
- Naviguer sur AWS EC2 console.
- Créer une nouvelle instance. Dans ce projet j'ai utilisé Ubuntu 24.04 LTS AMI.
- Choisir t2.medium comme type d'instance. Vous pouvez utiliser t3.micro si vous êtes sur l'offre gratuit. 
- Créer une paire de clés pour l'accès SSH.

![ec2-image](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

### Configurer le groupe de sécurité :
Créer un groupe de sécurité avec le "inbound rules" suivant :
- Type: SSH, Protocol: TCP, Port: 22, Source: Votre IP
- Type: HTTP, Protocol: TCP, Port: 80, Source: 0.0.0.0/0
- Type: Custom TCP, Protocol: TCP, Port: 5000 (Flask), Source: 0.0.0.0/0
- Type: Custom TCP, Protocol: TCP, Port: 8080 (Jenkins), Source: 0.0.0.0/0

![sg-image](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

### Connecter à l'instance EC2 :
Utiliser CloudShell et suivre les étapes sur l'image ci-dessous pour s'y connecter. N'oubliez pas d'ajouter dans cloudshell votre pair de clés.

![ssh-image](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

# Etape 2: Installation des dépendances dans EC2

### Mettre à jour les packets système :
```bash
sudo apt update && sudo apt upgrade -y
```
### Installer Git, Docker et Docker Compose :
```bash
sudo apt install git
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```
### Ajouter l'utilisateur dans groupe Docker pour executer les commandes docker sans sudo :
```bash
sudo usermod -aG docker $USER
newgrp docker
```
### Vérifier que vous pouvez éxecuter les commandes docker sans sudo :
```bash
docker --version
docker compose version
```
# Etape 3: Installation et configuration de Jenkins 
Si vous avez utiliser t3.micro comme type d'image EC2 merci d'installer Jenkins directement dans le serveur EC2 sans passer par docker. Pour tout ce qui suit je vais utiliser docker pour installer Jenkins.

### Créer un Dockerfile basé sur l'image Jenkins :
Par défaut Jenkins ne peut pas éxecuter les commandes git, docker et docker compose. Alors nous allons installer ces trois packets à l'intérieur de Jenkins afin qu'il puisse éxecuter notre pipeline.
#### DockerfileJ
```bash
# Jenkins LTS officiel
FROM jenkins/jenkins:lts-slim-jdk21

# Passe en root pour installer des packages
USER root

# Installer Git et Docker CLI + Docker Compose v2
RUN apt-get update && \
    apt install git && \
    curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm -rf /var/lib/apt/lists/*

# Retour à l’utilisateur jenkins
USER jenkins
```
### Construire l'image Jenkins personnalisée  :

```bash
docker build -t jenkins-with-docker-git -f DockerfileJ .
```
### Créer un conteneur Jenkins avec l'image *jenkins-with-docker-git* :
```bash
docker run -d \
  --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --group-add $(getent group docker | cut -d: -f3) \
  jenkins-with-docker-git
```
- __`-v /var/run/docker.sock:/var/run/docker.sock`__ -> permet à Jenkins d’exécuter Docker sur le serveur hôte, sinon les conteneurs créés n’existeraient qu’à l’intérieur de Jenkins.
- __`--group-add <docker_gid>`__ -> ajoute l’utilisateur jenkins au groupe docker du host
- __`$(getent group docker | cut -d: -f3)`__ -> récupère l’ID du groupe docker sur l’hôte

### Configuration initiale de Jenkins :
- Récupérer le mot de passe admin initiale :
```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
- Accéder à l'interface web de Jenkins sur __`http://<ec2-public-ip>:8080`__
- Coller le mot de passe, installer les plugins et créer un utilisateur admin. 

# Etape 4: Configuration du dépôt GitHub
Voici les fichiers que vous avez besoin dans votre dépot GitHub

#### app.py

```bash
from flask import Flask, jsonify
import MySQLdb
import os  # <- nécessaire pour lire les variables d'environnement

# Lire les infos DB depuis variables d'environnement
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "flaskuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "flaskpass")
DB_NAME = os.environ.get("DB_NAME", "devops")

app = Flask(__name__)

def get_db_connection():
    conn = MySQLdb.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        db=DB_NAME
    )
    return conn

#home page
@app.route("/")
def home():
    return "Bonjour"

@app.route("/mysql")
def mysql_test():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    return f"MySQL test result: {result[0]}"

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

```
#### requirements.txt

```bash
flask==2.2.5
#pymysql==1.0.3
# ou si tu veux mysqlclient (plus "native"), remplace pymysql par mysqlclient
mysqlclient==2.1.1
```

#### Dockerfile

```bash
# Utilise l'image Python 3.9 basée sur Alpine Linux (plus légère)
FROM python:3.9-alpine

# Définit le répertoire de travail à l'intérieur du container
WORKDIR /two-tier-app

# Copie le fichier des dépendances Python dans le container
COPY requirements.txt .

# Installer les outils de compilation et dépendances nécessaires pour mysqlclient
# - gcc : compilateur C
# - musl-dev : librairie C standard pour Alpine
# - mariadb-connector-c-dev : headers et librairies pour MySQL/MariaDB
# - installe les dépendances Python listées dans requirements.txt
RUN apk add --no-cache gcc musl-dev mariadb-connector-c-dev \
    && pip install --no-cache-dir -r requirements.txt

# Copie tout le code de l'application dans le container
COPY . .

# Expose le port 5000 pour accéder à Flask depuis l'extérieur du container
EXPOSE 5000

# Commande pour lancer l'application Flask
# -u : mode unbuffered pour que les logs s'affichent en temps réel
CMD ["python","-u","app.py"]
```

#### docker-compose.yml

```bash

services:
  mysql:
    image: mariadb:lts-ubi9
    container_name: mariadb
    environment:
      MYSQL_DATABASE: "devops"
      MYSQL_USER: "flaskuser"
      MYSQL_PASSWORD: "flaskpass"
      MYSQL_ROOT_PASSWORD: "root" # root pour administration, pas pour Flask
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
    restart: always
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uflaskuser", "-pflaskpass"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 60s

  flask:
    build: .
    container_name: two-tier-app
    ports:
      - "5000:5000"
    environment:
      - DB_HOST=mysql
      - DB_USER=flaskuser
      - DB_PASSWORD=flaskpass
      - DB_NAME=devops
    depends_on:
      - mysql
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 60s

volumes:
  mysql-data:

```

#### Jenkinsfile

```bash
pipeline {
    agent any

    stages {
        stage('Clone Repository') {
            steps {
                // My github repos
                git branch: 'main', url: 'https://github.com/alphonse-r/two-tier-app.git'
            }
        }

        stage('Deploy Application with Docker Compose') {
            steps {
                // Arrêter les containers existants (si présents)
                sh 'docker compose down || true'

                // Lancer Flask + MySQL, reconstruire l'image Flask si nécessaire
                sh 'docker compose up -d --build'
            }
        }
    }

    post {
        always {
            // Affiche l'état des containers après déploiement
            sh 'docker compose ps'
        }
        success {
            echo 'Déploiement réussi !'
        }
        failure {
            echo 'Erreur pendant le déploiement'
        }
    }
}
```

### Modifier Webhook dans github
Va sur ***`settings - Webhooks - Edit`*** dans votre projet.
Configure webhook comme suit :
- ***`Payload URL*`*** -> ***`http://<ec2-public-ip>:8080/github-webhook/`***
- ***`Content type*`*** -> ***`application/json`***
- Ensuite cliquer sur ***`Update webhook`***

![webhook](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

# Etape 5: Création et Execution de pipeline Jenkins

### Créer un nouveau job pipeline dans Jenkins :
- Depuis le tableau de bord Jenkins, sélectionnez *New Item*.
- Donnez un nom au projet, choisissez Pipeline, puis cliquez sur OK.

### Configurer le pipeline :
- Dans la configuration du projet, faites défiler jusqu’à la section ***`Pipeline`***.
- Définissez ***`Definition`*** sur ***`Pipeline script from SCM`***.
- Choisissez ***`Git`*** comme système de gestion de code source.
- Saisissez l’URL de votre dépôt GitHub.
- Vérifiez que le Script Path est bien ***`Jenkinsfile`***.
- Changer ****`/master`*** en ****`/main`***
- Enregistrez la configuration.

![pipeline-image](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

### Executer le pipeline:

- Cliquez sur Build Now pour déclencher manuellement le pipeline pour la première fois.
- Surveillez l’exécution via Stage View ou Console Output.

![output-image](https://via.placeholder.com/468x300?text=App+Screenshot+Here)

### Vérifier le déploiement :

- Après un build réussi, votre application Flask sera accessible à l’adresse : **`http://<votre-ip-publique-EC2>:5000`**.
- Vérifiez que les conteneurs sont bien en cours d’exécution sur l’instance EC2 avec la commande **docker ps**.

