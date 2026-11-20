from app.errors import BusinessError


def approval(result):
    balance = result["reconcile"]
    if balance["status"] != "MATCHED":
        raise BusinessError("UNBALANCED", "炉批尚未对平", 409)
    accepted = balance["goal_met"] and balance["unproven_s"] == 0
    return {
        "status": "RELEASED" if accepted else "REVIEW",
        "batch": result["intake"]["plan"]["batch"],
        "decision": "轨道证据齐全" if accepted else "转工艺复核",
    }
