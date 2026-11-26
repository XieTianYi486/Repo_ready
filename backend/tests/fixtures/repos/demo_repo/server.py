import os

from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    # Environment variables are documented in .env.example.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
