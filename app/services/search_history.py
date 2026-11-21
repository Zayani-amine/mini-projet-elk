import re
from datetime import datetime

from app.services.mongo import get_database


def get_searches_collection():
    return get_database().get_collection("searches")


def serialize_search(document):
    data = dict(document)
    data["id"] = str(data.pop("_id"))
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat()
    filters = dict(data.get("filters") or {})
    for field in ("date_from", "date_to"):
        if isinstance(filters.get(field), datetime):
            filters[field] = filters[field].isoformat()
    data["filters"] = filters
    return data


def record_search(document):
    result = get_searches_collection().insert_one(document)
    return str(result.inserted_id)


def list_searches(page, size, query):
    collection = get_searches_collection()
    selector = {}
    if query:
        selector["query"] = {"$regex": re.escape(query), "$options": "i"}
    total = collection.count_documents(selector)
    documents = list(
        collection.find(selector)
        .sort("created_at", -1)
        .skip((page - 1) * size)
        .limit(size)
    )
    return {
        "results": [serialize_search(document) for document in documents],
        "total": total,
        "page": page,
        "size": size,
    }
