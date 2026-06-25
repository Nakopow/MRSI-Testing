from __future__ import annotations

import os
import re
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

auth_bp = Blueprint("auth", __name__)

# ── Google OAuth (optional) ───────────────────────────────────────────────────

try:
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    _AUTHLIB_AVAILABLE = True
except ImportError:
    oauth = None
    _AUTHLIB_AVAILABLE = False


def _google_configured() -> bool:
    return (
        _AUTHLIB_AVAILABLE
        and bool(os.environ.get("GOOGLE_CLIENT_ID"))
        and bool(os.environ.get("GOOGLE_CLIENT_SECRET"))
    )


def _is_email_allowed(email: str) -> bool:
    allowed_raw = os.environ.get("ALLOWED_GMAIL", "").strip()
    if not allowed_raw:
        return True
    allowed = {e.strip().lower() for e in allowed_raw.split(",") if e.strip()}
    return email.lower() in allowed


def _slugify_username(name: str) -> str:
    """Turn a display name into a safe username slug."""
    slug = re.sub(r"[^a-zA-Z0-9_]", "", name.replace(" ", "_"))
    return slug[:30] or "user"


def _unique_username(base: str) -> str:
    """Return *base* or *base_N* so the username is unique in the DB."""
    from models import User
    candidate = base
    n = 1
    while User.query.filter_by(username=candidate).first():
        candidate = f"{base}_{n}"
        n += 1
    return candidate


# ── Auth guard ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login_page", next=request.path))
        return f(*args, **kwargs)
    return decorated


def _start_session(user) -> None:
    """Write user info into the Flask session."""
    from models import db
    user.last_login = datetime.utcnow()
    db.session.commit()
    session.permanent = True
    session["logged_in"] = True
    session["user_id"] = user.id
    session["username"] = user.username
    session["avatar"] = user.avatar or ""


# ── Registration ──────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        from models import User, db

        if not username or not password:
            error = "Username and password are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."
        elif email and User.query.filter_by(email=email).first():
            error = "An account with that email already exists."
        else:
            user = User(username=username, email=email or None)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            _start_session(user)
            return redirect(url_for("dashboard.dashboard"))

    return render_template(
        "auth/register.html",
        error=error,
        google_enabled=_google_configured(),
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard"))

    error = None
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password   = request.form.get("password", "")

        from models import User
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if not user or not user.check_password(password):
            error = "Invalid username or password."
        else:
            _start_session(user)
            next_url = request.args.get("next") or url_for("dashboard.dashboard")
            return redirect(next_url)

    return render_template(
        "auth/login.html",
        error=error,
        google_enabled=_google_configured(),
    )


# ── Google OAuth ──────────────────────────────────────────────────────────────

@auth_bp.route("/auth/google")
def google_login():
    if not _google_configured():
        return redirect(url_for("auth.login_page"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    state = request.args.get("next", "")
    return oauth.google.authorize_redirect(redirect_uri, state=state)


@auth_bp.route("/auth/google/callback")
def google_callback():
    if not _google_configured():
        return redirect(url_for("auth.login_page"))

    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        return render_template(
            "auth/login.html",
            error="Google sign-in was cancelled or failed. Please try again.",
            google_enabled=_google_configured(),
        )

    info      = token.get("userinfo") or {}
    email     = (info.get("email") or "").strip().lower()
    google_id = info.get("sub", "")

    if not email:
        return render_template(
            "auth/login.html",
            error="Could not get your email from Google. Make sure you granted email access.",
            google_enabled=_google_configured(),
        )

    if not _is_email_allowed(email):
        return render_template(
            "auth/login.html",
            error=f"Access denied: {email} is not on the allowed list.",
            google_enabled=_google_configured(),
        )

    from models import User, db

    # Find existing user by Google ID → email → create new
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
    if not user:
        base     = _slugify_username(info.get("name", email.split("@")[0]))
        username = _unique_username(base)
        user     = User(username=username, email=email, google_id=google_id)
        db.session.add(user)
    else:
        user.google_id = google_id   # link if found by email

    user.avatar = info.get("picture") or user.avatar
    db.session.flush()
    _start_session(user)

    next_url = request.args.get("state") or url_for("dashboard.dashboard")
    return redirect(next_url)


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))
