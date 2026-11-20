from app.modules.m1_intake.service import intake
from app.modules.m2_calibration.service import calibrate
from app.modules.m3_alignment.service import align
from app.modules.m4_soak.service import measure
from app.modules.m5_gaps.service import revisit
from app.modules.m6_reconcile.service import reconcile


def calculate(data):
    collected = intake(data)
    plan = collected["plan"]
    calibration = calibrate(data, collected)
    alignment = align(plan, calibration)
    soak = measure(data, plan, alignment)
    gaps = revisit(soak)
    return {
        "intake": collected,
        "calibration": calibration,
        "alignment": alignment,
        "soak": soak,
        "gaps": gaps,
        "reconcile": reconcile(collected, soak, gaps),
    }
