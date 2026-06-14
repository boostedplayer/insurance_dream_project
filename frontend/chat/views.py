import json
import uuid
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings

API = settings.FASTAPI_BASE_URL


def _auth_headers(request) -> dict:
    token = request.session.get("token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _is_logged_in(request) -> bool:
    return bool(request.session.get("token"))


# ── Login / Logout ─────────────────────────────────────────────────────────────

def login_view(request):
    if _is_logged_in(request):
        return redirect("chat")

    error = None

    if request.method == "POST":
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        try:
            resp = requests.post(
                f"{API}/api/auth/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                request.session["token"]   = data["access_token"]
                request.session["user_id"] = data["user_id"]
                request.session["name"]    = data["name"]
                return redirect("chat")
            else:
                error = resp.json().get("detail", "Invalid credentials")
        except requests.exceptions.ConnectionError:
            error = "Could not connect to the backend. Make sure FastAPI is running."

    return render(request, "login.html", {"error": error})


def logout_view(request):
    request.session.flush()
    return redirect("login")


# ── Register ──────────────────────────────────────────────────────────────────

def register_view(request):
    if _is_logged_in(request):
        return redirect("chat")

    error = None

    if request.method == "POST":
        name     = request.POST.get("name", "").strip()
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        city     = request.POST.get("city", "").strip()

        try:
            resp = requests.post(
                f"{API}/api/auth/register",
                json={"name": name, "email": email, "password": password, "city": city},
                timeout=10,
            )
            if resp.status_code == 201:
                data = resp.json()
                request.session["token"]   = data["access_token"]
                request.session["user_id"] = data["user_id"]
                request.session["name"]    = data["name"]
                return redirect("chat")
            else:
                error = resp.json().get("detail", "Registration failed. Please try again.")
        except requests.exceptions.ConnectionError:
            error = "Could not connect to the backend. Make sure FastAPI is running."

    return render(request, "register.html", {"error": error})


# ── Chat ───────────────────────────────────────────────────────────────────────

def chat_view(request):
    if not _is_logged_in(request):
        return redirect("login")

    if not request.session.get("session_id"):
        request.session["session_id"] = str(uuid.uuid4())

    return render(request, "chat.html", {
        "name":       request.session.get("name", "User"),
        "session_id": request.session["session_id"],
    })


@require_POST
def send_message(request):
    if not _is_logged_in(request):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    body       = json.loads(request.body)
    message    = body.get("message", "").strip()
    # session_id client (sidebar) se aata hai; fallback Django session pe
    session_id = body.get("session_id") or request.session.get("session_id")

    if not message:
        return JsonResponse({"error": "Empty message"}, status=400)

    try:
        resp = requests.post(
            f"{API}/api/chat",
            json={"message": message, "session_id": session_id},
            headers=_auth_headers(request),
            timeout=60,
        )
        if resp.status_code != 200:
            detail = resp.json().get("detail", resp.text)
            return JsonResponse({"error": f"Backend error ({resp.status_code}): {detail}"})
        data = resp.json()
        return JsonResponse({
            "response":     data.get("response", ""),
            "current_flow": data.get("current_flow"),
            "session_id":   data.get("session_id", session_id),
        })
    except requests.exceptions.Timeout:
        return JsonResponse({"error": "Agent took too long. Please try again."}, status=504)
    except requests.exceptions.ConnectionError:
        return JsonResponse({"error": "Backend unavailable."}, status=503)


@require_GET
def history(request):
    if not _is_logged_in(request):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    # session_id query param se (sidebar switching), fallback Django session pe
    session_id = request.GET.get("session_id") or request.session.get("session_id", "")

    try:
        resp = requests.get(
            f"{API}/api/chat/history/{session_id}",
            headers=_auth_headers(request),
            timeout=10,
        )
        return JsonResponse(resp.json())
    except requests.exceptions.ConnectionError:
        return JsonResponse({"messages": []})


# ── Chat sessions (sidebar proxies) ─────────────────────────────────────────────

def sessions(request):
    """GET → user ke sessions list karo; POST → naya session banao."""
    if not _is_logged_in(request):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    try:
        if request.method == "POST":
            resp = requests.post(f"{API}/api/chat/sessions", headers=_auth_headers(request), timeout=10)
        else:
            resp = requests.get(f"{API}/api/chat/sessions", headers=_auth_headers(request), timeout=10)
        return JsonResponse(resp.json(), status=resp.status_code)
    except requests.exceptions.ConnectionError:
        return JsonResponse({"error": "Backend unavailable."}, status=503)


@require_POST
def session_delete(request, session_id):
    if not _is_logged_in(request):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    try:
        resp = requests.delete(
            f"{API}/api/chat/sessions/{session_id}",
            headers=_auth_headers(request),
            timeout=10,
        )
        return JsonResponse(resp.json(), status=resp.status_code)
    except requests.exceptions.ConnectionError:
        return JsonResponse({"error": "Backend unavailable."}, status=503)


# ── User profile ────────────────────────────────────────────────────────────────

def profile_view(request):
    if not _is_logged_in(request):
        return redirect("login")

    error = saved = None

    try:
        if request.method == "POST":
            # Form fields ko types mein convert karo
            payload = _build_profile_payload(request.POST)
            resp = requests.put(
                f"{API}/api/auth/profile",
                json=payload,
                headers=_auth_headers(request),
                timeout=10,
            )
            if resp.status_code == 200:
                saved = True
                profile = resp.json()
            else:
                error = resp.json().get("detail", "Could not save profile.")
                profile = _fetch_profile(request)
        else:
            profile = _fetch_profile(request)
    except requests.exceptions.ConnectionError:
        error = "Could not connect to the backend."
        profile = {}

    return render(request, "profile.html", {
        "profile":     profile or {},
        "error":       error,
        "saved":       saved,
        "name":        request.session.get("name", "User"),
        "occupations": [
            "Bank Employee", "Business Owner", "Delivery Agent", "Doctor", "Driver",
            "Factory Worker", "Police Officer", "Software Engineer", "Student", "Teacher",
        ],
    })


def _fetch_profile(request) -> dict:
    resp = requests.get(f"{API}/api/auth/profile", headers=_auth_headers(request), timeout=10)
    return resp.json() if resp.status_code == 200 else {}


def _build_profile_payload(post) -> dict:
    """Django POST form se typed JSON payload banao — khaali fields skip kar do."""
    int_fields   = ["age", "claims_history", "dependents", "vehicle_age", "driving_violations", "annual_mileage"]
    float_fields = ["bmi"]
    bool_fields  = ["smoker", "chronic_disease"]
    str_fields   = ["name", "city", "gender", "income_category", "occupation",
                    "alcohol_consumption", "exercise_frequency", "marital_status"]

    payload = {}
    for f in str_fields:
        v = post.get(f, "").strip()
        if v:
            payload[f] = v
    for f in int_fields:
        v = post.get(f, "").strip()
        if v:
            try: payload[f] = int(v)
            except ValueError: pass
    for f in float_fields:
        v = post.get(f, "").strip()
        if v:
            try: payload[f] = float(v)
            except ValueError: pass
    for f in bool_fields:
        # checkbox/select — "Yes"/"true"/"on" → True
        payload[f] = post.get(f, "").strip().lower() in {"yes", "true", "on", "1"}
    return payload


# ── Admin — Claims Review ──────────────────────────────────────────────────────

def admin_claims_view(request):
    if not _is_logged_in(request):
        return redirect("login")

    try:
        resp   = requests.get(f"{API}/api/admin/claims/pending", headers=_auth_headers(request), timeout=10)
        claims = resp.json() if resp.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        claims = []

    return render(request, "admin_claims.html", {"claims": claims})


@require_POST
def admin_claim_decision(request, claim_id):
    if not _is_logged_in(request):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    body = json.loads(request.body)
    try:
        resp = requests.post(
            f"{API}/api/admin/claims/{claim_id}/decision",
            json=body,
            headers=_auth_headers(request),
            timeout=10,
        )
        return JsonResponse(resp.json(), status=resp.status_code)
    except requests.exceptions.ConnectionError:
        return JsonResponse({"error": "Backend unavailable."}, status=503)


# ── Admin — Support Tickets ────────────────────────────────────────────────────

def admin_tickets_view(request):
    if not _is_logged_in(request):
        return redirect("login")

    try:
        resp    = requests.get(f"{API}/api/admin/tickets", headers=_auth_headers(request), timeout=10)
        tickets = resp.json() if resp.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        tickets = []

    return render(request, "admin_tickets.html", {"tickets": tickets})


@require_POST
def admin_close_ticket(request, ticket_id):
    if not _is_logged_in(request):
        return JsonResponse({"error": "Not authenticated"}, status=401)

    try:
        resp = requests.patch(
            f"{API}/api/admin/tickets/{ticket_id}/close",
            headers=_auth_headers(request),
            timeout=10,
        )
        return JsonResponse(resp.json(), status=resp.status_code)
    except requests.exceptions.ConnectionError:
        return JsonResponse({"error": "Backend unavailable."}, status=503)
