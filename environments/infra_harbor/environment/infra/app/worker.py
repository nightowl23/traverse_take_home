"""Background worker process."""
import time
import os
import redis


def get_redis():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(redis_url)


def main():
    r = get_redis()
    print("Worker started, listening for tasks...")
    while True:
        task = r.blpop("tasks", timeout=5)
        if task:
            print(f"Processing task: {task}")
        time.sleep(1)


if __name__ == "__main__":
    main()
