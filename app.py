import os
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
load_dotenv()
app = Flask(__name__)
FRONTEND_URL = os.getenv("FRONTEND_URL")
CORS(app, origins=[FRONTEND_URL] if FRONTEND_URL else "*")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
def json_response(response):
    """Return JSON from Supabase, or an empty object if the body is blank."""
    try:
        return response.json()
    except ValueError:
        return {}
def error(message, status):
    """Send one standard error response to the frontend."""
    return jsonify({"error": message}), status
def supabase_headers(token=None):
    """Create headers for Supabase Auth and database requests."""
    bearer = token or SUPABASE_KEY
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json"
    }
def supabase_request(method, path, token=None, **kwargs):
    """Call Supabase with a short reusable request helper."""
    return requests.request(
        method,
        f"{SUPABASE_URL}{path}",
        headers=supabase_headers(token),
        timeout=15,
        **kwargs
    )
def get_token():
    """Read the login token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    return auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
def get_current_user(token):
    """Return the Supabase user connected to the login token."""
    response = supabase_request("GET", "/auth/v1/user", token)
    return json_response(response) if response.status_code == 200 else None
def get_required_user():
    """Validate token and return both token and current user."""
    token = get_token()
    if not token:
        return None, None, error("Login token is required", 401)
    user = get_current_user(token)
    if not user:
        return token, None, error("Invalid or expired login token", 401)
    return token, user, None
def positive_number(value, message):
    """Convert a value to a number and confirm it is greater than zero."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, error(message, 400)
    if number <= 0:
        return None, error(message, 400)
    return number, None
def supabase_error(payload, fallback):
    """Pick the clearest error message Supabase returned."""
    if isinstance(payload, dict):
        return payload.get("message") or payload.get("msg") or payload.get("error") or fallback
    return fallback
@app.post("/api/signup")
def signup():
    """Create a new Supabase Auth user."""
    data = request.json or {}
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    confirm_password = data.get("confirmPassword")
    if not all([name, email, password, confirm_password]):
        return error("Name, email, password and confirm password are required", 400)
    if len(password) < 6:
        return error("Password must be at least 6 characters", 400)
    if password != confirm_password:
        return error("Password and confirm password must match", 400)
    response = supabase_request("POST", "/auth/v1/signup", json={
        "email": email,
        "password": password,
        "data": {"display_name": name}
    })
    return jsonify(json_response(response)), response.status_code
@app.post("/api/login")
def login():
    """Login user with email and password."""
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return error("Email and password are required", 400)
    response = supabase_request(
        "POST",
        "/auth/v1/token?grant_type=password",
        json={"email": email, "password": password}
    )
    return jsonify(json_response(response)), response.status_code
@app.get("/api/expenses")
def get_expenses():
    """Return expenses for the logged-in user."""
    token = get_token()
    if not token:
        return error("Login token is required", 401)
    response = supabase_request(
        "GET",
        "/rest/v1/expenses?select=*&order=created_at.desc",
        token
    )
    return jsonify(json_response(response)), response.status_code
@app.post("/api/expenses")
def add_expense():
    """Validate and save one expense for the logged-in user."""
    token, user, auth_error = get_required_user()
    if auth_error:
        return auth_error
    data = request.json or {}
    amount, amount_error = positive_number(data.get("amount"), "Amount must be greater than 0")
    if not data.get("title"):
        return error("Title is required", 400)
    if amount_error:
        return amount_error
    if not data.get("category"):
        return error("Category is required", 400)
    expense = {
        "user_id": user["id"],
        "title": data["title"],
        "amount": amount,
        "type": data.get("type", "Individual"),
        "category": data["category"],
        "expense_date": data.get("date")
    }
    headers = {**supabase_headers(token), "Prefer": "return=representation"}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/expenses", headers=headers, json=expense, timeout=15)
    payload = json_response(response)
    if response.status_code >= 400:
        return error(supabase_error(payload, "Could not add expense."), response.status_code)
    return jsonify(payload), response.status_code
@app.delete("/api/expenses/<expense_id>")
def delete_expense(expense_id):
    """Delete one expense owned by the logged-in user."""
    token = get_token()
    if not token:
        return error("Login token is required", 401)
    response = supabase_request("DELETE", f"/rest/v1/expenses?id=eq.{expense_id}", token)
    return jsonify({"message": "Expense deleted"}), response.status_code
@app.get("/api/budget")
def get_budget():
    """Return the latest budget for the logged-in user."""
    token = get_token()
    if not token:
        return error("Login token is required", 401)
    response = supabase_request(
        "GET",
        "/rest/v1/budgets?select=*&order=created_at.desc&limit=1",
        token
    )
    return jsonify(json_response(response)), response.status_code
@app.post("/api/budget")
def save_budget():
    """Validate and save a budget for the logged-in user."""
    token, user, auth_error = get_required_user()
    if auth_error:
        return auth_error
    data = request.json or {}
    amount, amount_error = positive_number(data.get("amount"), "Budget must be greater than 0")
    if amount_error:
        return amount_error
    budget = {"user_id": user["id"], "month": data.get("month"), "amount": amount}
    headers = {**supabase_headers(token), "Prefer": "return=representation"}
    response = requests.post(f"{SUPABASE_URL}/rest/v1/budgets", headers=headers, json=budget, timeout=15)
    payload = json_response(response)
    if response.status_code >= 400:
        return error(supabase_error(payload, "Budget not saved."), response.status_code)
    return jsonify(payload), response.status_code
if __name__ == "__main__":
    app.run(debug=False, port=int(os.getenv("PORT", 5000)))
