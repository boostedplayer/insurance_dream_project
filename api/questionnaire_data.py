"""
Canonical 30-question insurance risk-profiling questionnaire.

This is the single source of truth for the onboarding MCQs shown to a user the
FIRST time they sign up (before they reach the chat). The answers are:
  1. stored raw in `risk_questionnaire_responses` (audit / future modelling), and
  2. mapped onto the `users` demographic columns that the ML risk model consumes,
     so the agent can immediately suggest the right insurance.

Each question:
  key      — stable identifier (also the form field name)
  field    — `users` column it maps to, or None for "raw only" questions
  cast     — how the chosen value is cast before it is written to `users`
             ("int" | "float" | "bool" | "str")
  question — text shown to the user
  options  — list of {label, value}. `value` for a mapped question MUST be a
             canonical value the ML model was trained on (see the risk dataset).

Numeric fields (age, bmi, mileage, …) are asked as ranges; `value` is a
representative number inside that range.
"""

QUESTIONS = [
    # ── Core demographics (mapped to ML model fields) ──────────────────────────
    {
        "key": "age", "field": "age", "cast": "int",
        "question": "What is your age group?",
        "options": [
            {"label": "18 – 25", "value": "23"},
            {"label": "26 – 35", "value": "30"},
            {"label": "36 – 45", "value": "41"},
            {"label": "46 – 55", "value": "50"},
            {"label": "56 – 65", "value": "60"},
            {"label": "65+",     "value": "67"},
        ],
    },
    {
        "key": "gender", "field": "gender", "cast": "str",
        "question": "What is your gender?",
        "options": [
            {"label": "Male",   "value": "Male"},
            {"label": "Female", "value": "Female"},
        ],
    },
    {
        "key": "city", "field": "city", "cast": "str",
        "question": "Which city do you primarily live in?",
        "options": [
            {"label": "Mumbai",    "value": "Mumbai"},
            {"label": "Delhi",     "value": "Delhi"},
            {"label": "Bangalore", "value": "Bangalore"},
            {"label": "Hyderabad", "value": "Hyderabad"},
            {"label": "Chennai",   "value": "Chennai"},
            {"label": "Kolkata",   "value": "Kolkata"},
            {"label": "Pune",      "value": "Pune"},
            {"label": "Ahmedabad", "value": "Ahmedabad"},
        ],
    },
    {
        "key": "marital_status", "field": "marital_status", "cast": "str",
        "question": "What is your marital status?",
        "options": [
            {"label": "Single",  "value": "Single"},
            {"label": "Married", "value": "Married"},
        ],
    },
    {
        "key": "dependents", "field": "dependents", "cast": "int",
        "question": "How many people financially depend on you?",
        "options": [
            {"label": "None",       "value": "0"},
            {"label": "1",          "value": "1"},
            {"label": "2",          "value": "2"},
            {"label": "3",          "value": "3"},
            {"label": "4",          "value": "4"},
            {"label": "5 or more",  "value": "5"},
        ],
    },
    {
        "key": "income_category", "field": "income_category", "cast": "str",
        "question": "Which best describes your annual household income?",
        "options": [
            {"label": "Under ₹3 lakh",       "value": "Low"},
            {"label": "₹3 – 6 lakh",         "value": "Lower Middle"},
            {"label": "₹6 – 12 lakh",        "value": "Middle"},
            {"label": "₹12 – 25 lakh",       "value": "Upper Middle"},
            {"label": "Above ₹25 lakh",      "value": "High"},
        ],
    },
    {
        "key": "occupation", "field": "occupation", "cast": "str",
        "question": "What is your occupation?",
        "options": [
            {"label": "Software Engineer", "value": "Software Engineer"},
            {"label": "Doctor",            "value": "Doctor"},
            {"label": "Bank Employee",     "value": "Bank Employee"},
            {"label": "Teacher",           "value": "Teacher"},
            {"label": "Business Owner",    "value": "Business Owner"},
            {"label": "Police Officer",    "value": "Police Officer"},
            {"label": "Factory Worker",    "value": "Factory Worker"},
            {"label": "Driver",            "value": "Driver"},
            {"label": "Delivery Agent",    "value": "Delivery Agent"},
            {"label": "Student",           "value": "Student"},
        ],
    },

    # ── Health & lifestyle (mapped) ────────────────────────────────────────────
    {
        "key": "smoker", "field": "smoker", "cast": "bool",
        "question": "Do you smoke or use tobacco products?",
        "options": [
            {"label": "No, never",            "value": "no"},
            {"label": "Yes, occasionally",    "value": "yes"},
            {"label": "Yes, regularly",       "value": "yes"},
        ],
    },
    {
        "key": "alcohol_consumption", "field": "alcohol_consumption", "cast": "str",
        "question": "How often do you consume alcohol?",
        "options": [
            {"label": "Never",        "value": "None"},
            {"label": "Occasionally", "value": "Occasional"},
            {"label": "Frequently",   "value": "Frequent"},
        ],
    },
    {
        "key": "exercise_frequency", "field": "exercise_frequency", "cast": "str",
        "question": "How often do you exercise?",
        "options": [
            {"label": "Never",            "value": "Never"},
            {"label": "Rarely",           "value": "Rarely"},
            {"label": "Weekly",           "value": "Weekly"},
            {"label": "Daily",            "value": "Daily"},
        ],
    },
    {
        "key": "bmi", "field": "bmi", "cast": "float",
        "question": "Which best describes your body type / BMI range?",
        "options": [
            {"label": "Underweight (BMI under 18.5)",   "value": "17.5"},
            {"label": "Normal (BMI 18.5 – 24.9)",       "value": "22.0"},
            {"label": "Overweight (BMI 25 – 29.9)",     "value": "27.0"},
            {"label": "Obese (BMI 30+)",                "value": "32.0"},
        ],
    },
    {
        "key": "chronic_disease", "field": "chronic_disease", "cast": "bool",
        "question": "Have you been diagnosed with any chronic illness "
                    "(e.g. diabetes, hypertension, heart/kidney disease)?",
        "options": [
            {"label": "No", "value": "no"},
            {"label": "Yes", "value": "yes"},
        ],
    },
    {
        "key": "claims_history", "field": "claims_history", "cast": "int",
        "question": "How many insurance claims have you filed in the last 5 years?",
        "options": [
            {"label": "None",      "value": "0"},
            {"label": "1",         "value": "1"},
            {"label": "2",         "value": "2"},
            {"label": "3",         "value": "3"},
            {"label": "4",         "value": "4"},
            {"label": "5 or more", "value": "5"},
        ],
    },

    # ── Motor / driving (mapped) ───────────────────────────────────────────────
    {
        "key": "vehicle_age", "field": "vehicle_age", "cast": "int",
        "question": "How old is your primary vehicle?",
        "options": [
            {"label": "I don't own a vehicle", "value": "0"},
            {"label": "Brand new (under 1 yr)", "value": "0"},
            {"label": "1 – 3 years",            "value": "2"},
            {"label": "4 – 7 years",            "value": "5"},
            {"label": "8 – 12 years",           "value": "10"},
            {"label": "Over 12 years",          "value": "14"},
        ],
    },
    {
        "key": "driving_violations", "field": "driving_violations", "cast": "int",
        "question": "How many traffic/driving violations have you had in the last 3 years?",
        "options": [
            {"label": "None",      "value": "0"},
            {"label": "1",         "value": "1"},
            {"label": "2",         "value": "2"},
            {"label": "3",         "value": "3"},
            {"label": "4 or more", "value": "5"},
        ],
    },
    {
        "key": "annual_mileage", "field": "annual_mileage", "cast": "int",
        "question": "Roughly how many kilometres do you drive per year?",
        "options": [
            {"label": "I don't drive",        "value": "0"},
            {"label": "Under 5,000 km",       "value": "4543"},
            {"label": "5,000 – 12,000 km",    "value": "8094"},
            {"label": "12,000 – 20,000 km",   "value": "15000"},
            {"label": "Over 20,000 km",       "value": "23599"},
        ],
    },

    # ── Coverage intent & extended risk profile (stored raw, not in ML model) ──
    {
        "key": "primary_interest", "field": None, "cast": "str",
        "question": "Which type of insurance are you most interested in?",
        "options": [
            {"label": "Health insurance",        "value": "health"},
            {"label": "Motor / vehicle insurance", "value": "motor"},
            {"label": "Life insurance",          "value": "life"},
            {"label": "Not sure / multiple",     "value": "multiple"},
        ],
    },
    {
        "key": "existing_coverage", "field": None, "cast": "str",
        "question": "Do you currently hold any insurance policy?",
        "options": [
            {"label": "No, this is my first",     "value": "none"},
            {"label": "Yes, health only",         "value": "health"},
            {"label": "Yes, motor only",          "value": "motor"},
            {"label": "Yes, life only",           "value": "life"},
            {"label": "Yes, multiple policies",   "value": "multiple"},
        ],
    },
    {
        "key": "coverage_budget", "field": None, "cast": "str",
        "question": "What yearly premium budget are you comfortable with?",
        "options": [
            {"label": "Under ₹5,000",      "value": "lt_5k"},
            {"label": "₹5,000 – 15,000",   "value": "5k_15k"},
            {"label": "₹15,000 – 50,000",  "value": "15k_50k"},
            {"label": "Above ₹50,000",     "value": "gt_50k"},
        ],
    },
    {
        "key": "coverage_amount_pref", "field": None, "cast": "str",
        "question": "How much coverage (sum insured) are you looking for?",
        "options": [
            {"label": "Up to ₹5 lakh",     "value": "upto_5l"},
            {"label": "₹5 – 25 lakh",      "value": "5l_25l"},
            {"label": "₹25 lakh – 1 crore", "value": "25l_1cr"},
            {"label": "Above ₹1 crore",    "value": "gt_1cr"},
        ],
    },
    {
        "key": "family_medical_history", "field": None, "cast": "str",
        "question": "Is there a history of serious illness (cancer, heart disease, "
                    "diabetes) in your immediate family?",
        "options": [
            {"label": "No",            "value": "no"},
            {"label": "Yes, one side", "value": "partial"},
            {"label": "Yes, both sides", "value": "yes"},
            {"label": "Not sure",      "value": "unknown"},
        ],
    },
    {
        "key": "diet_type", "field": None, "cast": "str",
        "question": "How would you describe your typical diet?",
        "options": [
            {"label": "Balanced & home-cooked", "value": "balanced"},
            {"label": "Mostly vegetarian",      "value": "vegetarian"},
            {"label": "Frequent fast/junk food", "value": "junk"},
            {"label": "Irregular meals",        "value": "irregular"},
        ],
    },
    {
        "key": "sleep_hours", "field": None, "cast": "str",
        "question": "On average, how many hours do you sleep per night?",
        "options": [
            {"label": "Less than 5",  "value": "lt_5"},
            {"label": "5 – 6",        "value": "5_6"},
            {"label": "7 – 8",        "value": "7_8"},
            {"label": "More than 8",  "value": "gt_8"},
        ],
    },
    {
        "key": "stress_level", "field": None, "cast": "str",
        "question": "How would you rate your day-to-day stress level?",
        "options": [
            {"label": "Low",       "value": "low"},
            {"label": "Moderate",  "value": "moderate"},
            {"label": "High",      "value": "high"},
            {"label": "Very high", "value": "very_high"},
        ],
    },
    {
        "key": "health_checkup", "field": None, "cast": "str",
        "question": "How often do you get a full-body health check-up?",
        "options": [
            {"label": "Every year",        "value": "yearly"},
            {"label": "Every 2 – 3 years", "value": "few_years"},
            {"label": "Rarely",            "value": "rarely"},
            {"label": "Never",             "value": "never"},
        ],
    },
    {
        "key": "high_risk_hobbies", "field": None, "cast": "str",
        "question": "Do you regularly take part in high-risk activities "
                    "(biking, climbing, scuba, motorsport)?",
        "options": [
            {"label": "No",              "value": "no"},
            {"label": "Occasionally",    "value": "sometimes"},
            {"label": "Yes, frequently", "value": "yes"},
        ],
    },
    {
        "key": "international_travel", "field": None, "cast": "str",
        "question": "How often do you travel internationally?",
        "options": [
            {"label": "Never",            "value": "never"},
            {"label": "Once in a while",  "value": "occasional"},
            {"label": "Several times a year", "value": "frequent"},
        ],
    },
    {
        "key": "vehicle_type", "field": None, "cast": "str",
        "question": "What type of vehicle do you primarily use?",
        "options": [
            {"label": "None",            "value": "none"},
            {"label": "Two-wheeler",     "value": "two_wheeler"},
            {"label": "Hatchback",       "value": "hatchback"},
            {"label": "Sedan",           "value": "sedan"},
            {"label": "SUV",             "value": "suv"},
            {"label": "Commercial vehicle", "value": "commercial"},
        ],
    },
    {
        "key": "vehicle_use", "field": None, "cast": "str",
        "question": "How is your vehicle mainly used?",
        "options": [
            {"label": "I don't drive",       "value": "none"},
            {"label": "Personal / commute",  "value": "personal"},
            {"label": "Business / commercial", "value": "commercial"},
            {"label": "Mixed",               "value": "mixed"},
        ],
    },
    {
        "key": "driving_experience", "field": None, "cast": "str",
        "question": "How many years of driving experience do you have?",
        "options": [
            {"label": "I don't drive",  "value": "none"},
            {"label": "Under 2 years",  "value": "lt_2"},
            {"label": "2 – 5 years",    "value": "2_5"},
            {"label": "5 – 10 years",   "value": "5_10"},
            {"label": "Over 10 years",  "value": "gt_10"},
        ],
    },
]

# Quick lookups
_QUESTION_BY_KEY = {q["key"]: q for q in QUESTIONS}
_VALID_VALUES = {q["key"]: {o["value"] for o in q["options"]} for q in QUESTIONS}

# Profile columns this questionnaire is allowed to write (whitelist for safe SQL)
MAPPED_FIELDS = [q["field"] for q in QUESTIONS if q["field"]]


def _cast(value: str, cast: str):
    if cast == "int":
        return int(value)
    if cast == "float":
        return float(value)
    if cast == "bool":
        return str(value).strip().lower() in {"yes", "true", "on", "1"}
    return value


def validate_answers(answers: dict) -> list[str]:
    """Return a list of human-readable problems; empty list means all good."""
    problems = []
    for q in QUESTIONS:
        key = q["key"]
        if key not in answers or answers[key] in (None, ""):
            problems.append(f"Missing answer for '{key}'")
        elif str(answers[key]) not in _VALID_VALUES[key]:
            problems.append(f"Invalid value for '{key}': {answers[key]!r}")
    return problems


def map_answers_to_profile(answers: dict) -> dict:
    """
    Convert the raw {key: value} answers into a dict of `users` column updates,
    ready for the ML risk model and the agent's recommendations.
    """
    profile: dict = {}
    for key, raw in answers.items():
        q = _QUESTION_BY_KEY.get(key)
        if not q or not q["field"] or raw in (None, ""):
            continue
        try:
            profile[q["field"]] = _cast(raw, q["cast"])
        except (ValueError, TypeError):
            continue
    return profile
