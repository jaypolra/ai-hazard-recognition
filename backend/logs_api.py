import csv
from fastapi import APIRouter

router = APIRouter()

@router.get("/logs")
def get_logs():
    logs = []
    try:
        with open("event_log.csv", "r") as f:
            reader = csv.DictReader(f)
            logs = list(reader)
    except FileNotFoundError:
        pass
    return logs
