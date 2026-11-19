import os

from pymongo import MongoClient

_client = None


def get_client():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI is not set")
        _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    return _client


def get_files_collection():
    database = get_client().get_database("elk_logs")
    return database.get_collection("files")


def get_database():
    return get_client().get_database("elk_logs")
