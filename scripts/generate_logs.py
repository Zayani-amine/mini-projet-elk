import argparse
import csv
import json
import pathlib
import random
from datetime import datetime, timedelta, timezone

from faker import Faker

LOG_TYPES = ["capteurs", "alertes", "maintenance", "energie", "occupation"]
ZONES = ["Z1", "Z2", "Z3"]
FLOORS = [0, 1, 2, 3]
MEASURES = {
    "temperature": ("°C", 18.0, 33.0, 26.0, 30.0),
    "humidity": ("%", 30.0, 75.0, 65.0, 75.0),
    "luminosity": ("lux", 100.0, 900.0, None, None),
    "co2": ("ppm", 400.0, 1400.0, 1000.0, 1200.0),
}
ENERGY_TYPES = {"electricity": "kWh", "water": "m3", "heating": "kWh"}
EQUIPMENT_TYPES = ["hvac", "pump", "elevator"]


def iso(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_records(args):
    fake = Faker("fr_FR")
    Faker.seed(args.seed)
    random.seed(args.seed)
    records = {name: [] for name in LOG_TYPES}
    sensors = ["CAP-%04d" % number for number in range(1, args.sensors + 1)]
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=args.hours)

    for hour in range(args.hours):
        base = start + timedelta(hours=hour)
        for index, sensor in enumerate(sensors):
            zone = ZONES[index % len(ZONES)]
            floor = FLOORS[index % len(FLOORS)]
            measure = fake.random_element(elements=list(MEASURES))
            unit, low, high, warning, critical = MEASURES[measure]
            value = round(random.uniform(low, high), 2)
            breached = warning is not None and value > warning
            status = "faulty" if random.random() < 0.02 else "ok"
            moment = base + timedelta(minutes=fake.random_int(min=0, max=59))
            records["capteurs"].append({
                "@timestamp": iso(moment),
                "log_type": "capteurs",
                "sensor_id": sensor,
                "zone": zone,
                "floor": floor,
                "measure": measure,
                "value": value,
                "unit": unit,
                "status": status,
                "threshold_breached": breached,
            })
            if breached:
                severity = "critical" if critical is not None and value > critical else "warning"
                threshold = critical if severity == "critical" else warning
                records["alertes"].append({
                    "@timestamp": iso(moment + timedelta(seconds=1)),
                    "log_type": "alertes",
                    "alert_id": "ALT-%06d" % (len(records["alertes"]) + 1),
                    "sensor_id": sensor,
                    "zone": zone,
                    "measure": measure,
                    "severity": severity,
                    "rule": "%s_%s" % (measure, severity),
                    "value": value,
                    "threshold": float(threshold),
                })

        for zone in ZONES:
            energy_type = fake.random_element(elements=list(ENERGY_TYPES))
            quantity = round(random.uniform(15.0, 120.0), 2)
            records["energie"].append({
                "@timestamp": iso(base + timedelta(minutes=30)),
                "log_type": "energie",
                "meter_id": "CPT-%s" % zone,
                "zone": zone,
                "energy_type": energy_type,
                "quantity": quantity,
                "unit": ENERGY_TYPES[energy_type],
                "threshold_breached": quantity > 100.0,
            })
            capacity = fake.random_int(min=40, max=120)
            present_count = fake.random_int(min=0, max=capacity)
            records["occupation"].append({
                "@timestamp": iso(base + timedelta(minutes=45)),
                "log_type": "occupation",
                "room_id": "SAL-%s-%d" % (zone, FLOORS[index % len(FLOORS)]),
                "zone": zone,
                "present_count": present_count,
                "capacity": capacity,
                "occupancy_rate": round(present_count / capacity * 100, 2),
            })

    for index, sensor in enumerate(sensors):
        if random.random() >= 0.12:
            continue
        wear_level = round(random.uniform(0.0, 100.0), 2)
        records["maintenance"].append({
            "@timestamp": iso(now),
            "log_type": "maintenance",
            "equipment_id": "EQP-%04d" % (index + 1),
            "equipment_type": fake.random_element(elements=EQUIPMENT_TYPES),
            "zone": ZONES[index % len(ZONES)],
            "wear_level": wear_level,
            "predicted_failure": wear_level > 75.0,
            "estimated_due_date": fake.date_between(start_date="today", end_date="+90d").isoformat(),
        })

    return records


def write_records(records, stamp, args):
    output = pathlib.Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    inbox = pathlib.Path(args.inbox) if args.inbox else None
    if inbox:
        inbox.mkdir(parents=True, exist_ok=True)

    for log_type, rows in records.items():
        if not rows:
            continue
        if args.format in ("all", "json"):
            path = output / ("%s_%s.json" % (log_type, stamp))
            path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            if inbox:
                (inbox / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        if args.format in ("all", "csv", "txt"):
            fields = list(rows[0].keys())
            for extension, delimiter in (("csv", ","), ("txt", "|")):
                if args.format == "csv" and extension != "csv":
                    continue
                if args.format == "txt" and extension != "txt":
                    continue
                path = output / ("%s_%s.%s" % (log_type, stamp, extension))
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, delimiter=delimiter)
                    writer.writeheader()
                    writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Generate Smart Building IoT log samples.")
    parser.add_argument("--sensors", type=int, default=300)
    parser.add_argument("--hours", type=int, default=7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--format", choices=["all", "json", "csv", "txt"], default="all")
    parser.add_argument("--out", default="data/generated")
    parser.add_argument("--inbox", default=None)
    args = parser.parse_args()

    if args.sensors < 1 or args.hours < 1:
        parser.error("--sensors and --hours must be positive")

    records = build_records(args)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_records(records, stamp, args)
    print("GENERATED sensors=%d hours=%d stamp=%s" % (args.sensors, args.hours, stamp))
    for log_type, rows in records.items():
        print("%s=%d" % (log_type, len(rows)))


if __name__ == "__main__":
    main()
