def get_risk_category(score):

    if score >= 90:
        return "very_high"

    elif score >= 80:
        return "high"

    elif score >= 70:
        return "upper_middle"

    elif score >= 60:
        return "middle"

    elif score >= 50:
        return "lower_middle"

    elif score >= 25:
        return "low"

    return "very_low"

RISK_LOADING = {
"very_low": 0.00,
"low": 0.05,
"lower_middle": 0.10,
"middle": 0.15,
"upper_middle": 0.25,
"high": 0.40,
"very_high": 0.60
}

