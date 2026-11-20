from app.modules.m1_intake.plan import inspect_plan
from app.modules.m1_intake.readings import collect_readings
from app.quality import rows


def intake(data):
    plan = inspect_plan(data.get("plan"))
    records = list(rows(data, "readings"))
    accepted, markers, rejected, notices = collect_readings(records, plan["zones"])
    return {
        "plan": plan,
        "points": accepted,
        "markers": markers,
        "isolated": rejected,
        "notices": notices,
        "counts": {
            "input": len(records),
            "accepted": len(accepted),
            "isolated": len(rejected),
            "duplicate": sum(item["code"] == "DUPLICATE_READING" for item in notices),
        },
    }
