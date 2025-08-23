from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from job_fetcher.job_updater import JobUpdater
from job_fetcher.job_sources import JobAggregator
import psycopg2
import psycopg2.extras
import os
import json
from datetime import datetime
import uuid
import logging
import secrets
from ai_engine.resume_parser import ResumeParser
from ai_engine.job_matcher import JobMatcher
from flask_mail import Mail, Message
import spacy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup Flask app
app = Flask(__name__, template_folder="frontend/templates", static_folder="frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here")

# Setup uploads
app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_FILE_SIZE", 16 * 1024 * 1024))  # 16MB

# Setup mail
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "aijobmatcher@gmail.com"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_USERNAME", "aijobmatcher@gmail.com"),
)
mail = Mail(app)

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Database config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "mydb"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
    "port": os.getenv("DB_PORT", "5432"),
}

# Logger Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AI Components
try:
    resume_parser = ResumeParser()
    job_matcher = JobMatcher()
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    logger.error(f"Error initializing AI components: {e}")
    resume_parser = None
    job_matcher = None
    nlp = None

# Initialize Job Updater and Aggregator
try:
    job_updater = JobUpdater(DB_CONFIG)
    job_updater.update_jobs_for_keywords()
    job_aggregator = JobAggregator()
    import atexit
    job_updater.start_background_updater(update_interval_hours=6)
    atexit.register(job_updater.stop_background_updater)
except Exception as e:
    logger.error(f"Error initializing Job Updater: {e}")

def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx'}

def track_user_login(user_id):
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user_login_history (user_id, login_time) VALUES (%s, %s)", (user_id, datetime.now()))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to track user login: {e}")

def get_filtered_jobs_for_user(user_skills, limit=50):
    if not user_skills:
        return []

    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Exclude manual jobs and ensure necessary fields exist
        cursor.execute("""
            SELECT * FROM jobs
            WHERE status='active' AND is_active=TRUE
              AND source != 'Manual'
              AND description IS NOT NULL
              AND requirements IS NOT NULL
            ORDER BY created_at DESC
        """)
        jobs = cursor.fetchall()
        cursor.close()
        conn.close()

        skills_lower = [skill.lower() for skill in user_skills]
        matched_jobs = []
        for job in jobs:
            job_text = (job.get('title', '') + ' ' + job.get('description', '') + ' ' + job.get('requirements', '')).lower()
            matched_skills = [skill for skill in skills_lower if skill in job_text]
            if matched_skills:
                match_score = (len(matched_skills) / len(skills_lower)) * 100
                job_copy = dict(job)
                job_copy['matched_skills'] = matched_skills
                job_copy['skill_match_count'] = len(matched_skills)
                job_copy['match_score'] = round(match_score, 2)
                matched_jobs.append(job_copy)

        matched_jobs.sort(key=lambda x: x['match_score'], reverse=True)

        return matched_jobs[:limit]

    except Exception as e:
        logger.error(f"Error filtering jobs for user: {e}")
        return []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        user_type = request.form.get("user_type", "job_seeker")

        if not email or not password:
            flash("Email and password required.", "danger")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            if not conn:
                flash("Database connection error.", "danger")
                return render_template("register.html")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already registered.", "danger")
                cursor.close()
                conn.close()
                return render_template("register.html")
            cursor.execute(
                "INSERT INTO users (email, password, first_name, last_name, user_type, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (email, hashed_password, first_name, last_name, user_type, datetime.now())
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Registration successful, please login.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            flash("Registration error.", "danger")
            return render_template("register.html")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            conn = get_db_connection()
            if not conn:
                flash("Database connection error.", "danger")
                return render_template("login.html")
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if not user:
                flash("User not found.", "danger")
                return render_template("login.html")

            if not check_password_hash(user["password"], password):
                flash("Incorrect password.", "danger")
                return render_template("login.html")

            session["user_id"] = user["user_id"]
            session["user_email"] = user["email"]
            session["user_type"] = user["user_type"]
            flash("Login successful.", "success")

            # Track user login asynchronously or here
            track_user_login(user["user_id"])

            return redirect(url_for("dashboard"))

        except Exception as e:
            logger.error(f"Login error: {e}")
            flash("Login failed due to server error.", "danger")
            return render_template("login.html")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    try:
        conn = get_db_connection()
        if not conn:
            flash("Database error.", "danger")
            return redirect(url_for("index"))

        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM resumes WHERE user_id=%s", (user_id,))
        resumes = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) as total_jobs FROM jobs WHERE status='active' AND is_active=TRUE
        """)
        total_jobs = cursor.fetchone().get("total_jobs", 0)

        cursor.execute("""
            SELECT * FROM resumes WHERE user_id=%s ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        resume = cursor.fetchone()
        user_skills = []
        if resume and resume.get("parsed_text"):
            try:
                user_skills = json.loads(resume["parsed_text"]).get("skills", [])
            except Exception:
                user_skills = []

        cursor.close()
        conn.close()

        matched_jobs = get_filtered_jobs_for_user(user_skills)

        best_score = max((job.get("match_score", 0) for job in matched_jobs), default=0)

        return render_template(
            "dashboard.html",
            resumes=resumes,
            total_jobs=total_jobs,
            matched_jobs=matched_jobs,
            best_score=best_score,
            user_skills=user_skills,
        )

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash("Failed to load dashboard.", "danger")
        return redirect(url_for("index"))

# Implement other routes similarly, with error handling and session checks.

if __name__ == "__main__":
    app.run(debug=True)
