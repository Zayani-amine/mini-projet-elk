import hashlib
import json
import os

import redis

_client = None


def get_client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "redis"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            db=0,
            socket_timeout=1,
            socket_connect_timeout=1,
            decode_responses=True,
        )
    return _client


def make_key(prefix, payload=None):
    if payload is None:
        return prefix
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return "%s:%s" % (prefix.rstrip(":"), digest)


def cached_value(key, ttl, producer):
    try:
        raw = get_client().get(key)
        if raw is not None:
            return json.loads(raw), True
    except (redis.RedisError, ValueError, TypeError):
        pass

    value = producer()
    try:
        get_client().setex(key, ttl, json.dumps(value, default=str))
    except (redis.RedisError, ValueError, TypeError):
        pass
    return value, False
