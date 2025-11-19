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

@app.route("/")
def home():
    return "Bonjour"

@app.route("/mysql")
def home():
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

