"""Simple Flask web application served by the infrastructure."""
from flask import Flask, jsonify
import os
import redis

app = Flask(__name__)


def get_redis():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url)


@app.route("/")
def index():
    return jsonify({"service": "web", "status": "ok"})


@app.route("/health")
def health():
    return jsonify({"healthy": True})


@app.route("/api/v1/hits")
def hits():
    r = get_redis()
    count = r.incr("hits")
    return jsonify({"hits": count})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
