from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive and running 24/7!"

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
