import base64
import json
import os
import urllib.error
import urllib.request


class ElasticsearchError(RuntimeError):
    pass


def post_json(path, body, timeout=5):
    host = os.environ.get("ELASTICSEARCH_HOST", "http://elasticsearch:9200").rstrip("/")
    username = os.environ.get("ELASTIC_USERNAME", "elastic")
    password = os.environ.get("ELASTIC_PASSWORD", "")
    request = urllib.request.Request(
        host + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = base64.b64encode(("%s:%s" % (username, password)).encode("utf-8"))
    request.add_header("Authorization", "Basic " + token.decode("ascii"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ElasticsearchError("Elasticsearch is not available: %s" % exc) from exc
