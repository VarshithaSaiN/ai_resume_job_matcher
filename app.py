from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from job_fetcher.job_updater import JobUpdater
from job_fetcher.job_sources import JobAggregator
import psycopg2
import psycopg2.extras
import os, json, uuid, logging, secrets, atexit
from datetime import datetime
from ai_engine.resume_parser import ResumeParser
from ai_engine.job_matcher import JobMatcher
from flask_mail import Mail, Message
import spacy
from dotenv import load_dotenv

# Load environment
load_dotenv()

# App setup
app = Flask(__name__,
            template_folder="frontend/templates",
            static_folder="frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "1109")
app.config.update(
    UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", "uploads/"),
    MAX_CONTENT_LENGTH=int(os.getenv("MAX_FILE_SIZE", 16777216)),
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME="aijobmatcher@gmail.com",
    MAIL_PASSWORD="uzih uzvu hdwv puzy",
    MAIL_DEFAULT_SENDER="aijobmatcher@gmail.com"
)
mail = Mail(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Database
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT")
}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AI & scraping
resume_parser = ResumeParser()
job_matcher = JobMatcher()
nlp = spacy.load("en_core_web_sm")
job_updater = JobUpdater(DB_CONFIG)
job_updater.update_jobs_for_keywords()
job_aggregator = JobAggregator()
job_updater.start_background_updater(update_interval_hours=6)
atexit.register(job_updater.stop_background_updater)

# Helpers
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"DB connect error: {e}")
        return None

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"pdf", "docx"}

def track_user_login(user_id):
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO user_login_history (user_id, login_time) VALUES (%s, %s)",
            (user_id, datetime.now())
        )
        conn.commit()
    except Exception as e:
        logger.error(f"track login error: {e}")
    finally:
        cur.close(); conn.close()

def get_filtered_jobs_for_user(user_skills, limit=50):
    if not user_skills: return []
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM jobs
        WHERE status='active' AND is_active=TRUE
          AND source!='Manual'
          AND description IS NOT NULL AND requirements IS NOT NULL
        ORDER BY created_at DESC
    """)
    jobs = cur.fetchall()
    cur.close(); conn.close()

    lower_skills = [s.lower() for s in user_skills]
    matches = []
    for job in jobs:
        text = f"{job['title']} {job['description']} {job['requirements']}".lower()
        count = sum(1 for s in lower_skills if s in text)
        if count:
            score = round((count/len(lower_skills))*100, 1)
            jd = dict(job); jd["match_score"] = score
            matches.append(jd)
    return sorted(matches, key=lambda j: j["match_score"], reverse=True)[:limit]

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search-jobs")
def search_jobs():
    query = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    source = request.args.get("source", "").strip()
    conn = get_db_connection(); jobs=[]; total=0
    if conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        base = """
            SELECT * FROM jobs
            WHERE status='active' AND is_active=TRUE
              AND source!='Manual'
              AND title NOT LIKE '%search%'
              AND (external_url IS NULL OR external_url NOT LIKE '%/jobs/search%')
        """
        params=[]
        if query:
            base += " AND (title ILIKE %s OR description ILIKE %s OR company ILIKE %s)"
            like=f"%{query}%"
            params+= [like, like, like]
        if location:
            base += " AND location ILIKE %s"; params.append(f"%{location}%")
        if source:
            base += " AND source=%s"; params.append(source)
        base += " ORDER BY created_at DESC LIMIT 50"
        cur.execute(base, params) if params else cur.execute(base)
        jobs = cur.fetchall(); total = len(jobs)
        cur.close(); conn.close()
    else:
        flash("DB error","danger")
    return render_template("job_search.html",
                           jobs=jobs,
                           total=total,
                           query=query,
                           location=location,
                           source=source)

@app.route("/job_search_personalized")
def job_search_personalized():
    if "user_id" not in session: return redirect(url_for("login"))
    conn = get_db_connection()
    if not conn: flash("DB error","danger"); return redirect(url_for("dashboard"))
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT parsed_text FROM resumes
        WHERE user_id=%s ORDER BY created_at DESC LIMIT 1
    """,(session["user_id"],))
    r=cur.fetchone(); cur.close(); conn.close()
    skills=[]
    if r and r[0]:
        try: skills=json.loads(r).get("skills",[])
        except: skills=[]
    jobs = get_filtered_jobs_for_user(skills)
    return render_template("job_search_personalized.html",
                           jobs=jobs,
                           total_jobs=len(jobs),
                           user_skills=skills)

@app.route("/match_jobs/<int:resume_id>")
def match_jobs(resume_id):
    if "user_id" not in session: return redirect(url_for("login"))
    conn=get_db_connection()
    if not conn: flash("DB error","danger"); return redirect(url_for("dashboard"))
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT parsed_text FROM resumes
        WHERE resume_id=%s AND user_id=%s
    """,(resume_id,session["user_id"]))
    r=cur.fetchone(); cur.close(); conn.close()
    if not r or not r[0]: flash("Resume not found","danger"); return redirect(url_for("dashboard"))
    try: skills=json.loads(r).get("skills",[])
    except: skills=[]
    jobs=get_filtered_jobs_for_user(skills,limit=100)
    enhanced=[]
    for job in jobs:
        if job_matcher:
            mr=job_matcher.calculate_match_score(
                r,job["description"],job["requirements"]
            )
            jd=dict(job)
            jd["detailed_match_score"]=mr["final_score"]
            jd["skills_breakdown"]=mr
            enhanced.append(jd)
        else:
            enhanced.append(job)
    enhanced.sort(key=lambda j:j.get("detailed_match_score",j["match_score"]),reverse=True)
    return render_template("job_matches.html",
                           jobs=enhanced,
                           resume_id=resume_id,
                           user_skills=skills,
                           total_matches=len(enhanced))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session: return redirect(url_for("login"))
    conn=get_db_connection(); resumes=[]; total_all=0; skills=[]
    if conn:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM resumes WHERE user_id=%s",(session["user_id"],))
        resumes=cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status='active' AND is_active=TRUE")
        total_all=cur.fetchone()[0]
        cur.execute("""
            SELECT parsed_text FROM resumes
            WHERE user_id=%s ORDER BY created_at DESC LIMIT 1
        """,(session["user_id"],))
        r=cur.fetchone()
        cur.close(); conn.close()
        if r and r:
            try: skills=json.loads(r).get("skills",[])
            except: skills=[]
    matched=get_filtered_jobs_for_user(skills,limit=10)
    best=max([j["match_score"] for j in matched],default=0)
    return render_template("dashboard.html",
                           resumes=resumes,
                           job_count=total_all,
                           matching_jobs_count=len(matched),
                           best_match_score=best,
                           jobs=matched,
                           user_skills=skills)

@app.route("/upload_resume", methods=["GET","POST"])
def upload_resume():
    if "user_id" not in session: return redirect(url_for("login"))
    parsed=None; existing=[]
    conn=get_db_connection()
    if conn:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM resumes WHERE user_id=%s ORDER BY created_at DESC",(session["user_id"],))
        existing=cur.fetchall()
        cur.close(); conn.close()
    if request.method=="POST":
        file=request.files.get("resume_file")
        if not file or not allowed_file(file.filename):
            flash("Upload PDF or DOCX","danger"); return redirect(request.url)
        fn=secure_filename(file.filename)
        un=f"{uuid.uuid4()}_{fn}"
        fp=os.path.join(app.config["UPLOAD_FOLDER"],un)
        file.save(fp)
        parsed=resume_parser.parse_resume(fp) if resume_parser else {}
        conn=get_db_connection()
        if conn:
            cur=conn.cursor()
            cur.execute("""
                SELECT 1 FROM resumes
                WHERE user_id=%s AND original_filename=%s
            """,(session["user_id"],fn))
            if cur.fetchone():
                flash("Already uploaded","warning")
            else:
                cur.execute("""
                    INSERT INTO resumes(user_id,original_filename,file_path,parsed_text,created_at)
                    VALUES(%s,%s,%s,%s,%s)
                """,(session["user_id"],fn,un,json.dumps(parsed),datetime.now()))
                conn.commit()
                flash("Uploaded","success")
            cur.close(); conn.close()
            return redirect(url_for("dashboard"))
    return render_template("upload_resume.html",
                           parsed_text=parsed,
                           existing_resumes=existing)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        email=request.form["email"]
        pwd=generate_password_hash(request.form["password"])
        fn,ln=request.form["first_name"],request.form["last_name"]
        ut=request.form.get("user_type","job_seeker")
        conn=get_db_connection()
        if conn:
            cur=conn.cursor()
            cur.execute("SELECT 1 FROM users WHERE email=%s",(email,))
            if cur.fetchone():
                flash("Email exists","danger"); conn.close(); return redirect(url_for("register"))
            cur.execute("""
                INSERT INTO users(first_name,last_name,email,password,user_type,created_at)
                VALUES(%s,%s,%s,%s,%s,%s)
            """,(fn,ln,email,pwd,ut,datetime.now()))
            conn.commit(); conn.close()
            flash("Registered","success"); return redirect(url_for("login"))
        flash("DB error","danger")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form["email"]
        pwd=request.form["password"]
        conn=get_db_connection()
        if conn:
            cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM users WHERE email=%s",(email,))
            user=cur.fetchone(); conn.close()
            if not user:
                flash("Email not found","danger")
            elif check_password_hash(user["password"],pwd):
                session.update(user_id=user["user_id"],user_name=user["first_name"],user_type=user["user_type"])
                track_user_login(user["user_id"])
                flash("Logged in","success"); return redirect(url_for("dashboard"))
            else:
                flash("Wrong password","danger")
        else:
            flash("DB error","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out","success"); return redirect(url_for("index"))

# ... (Admin cleanup routes unchanged) ...

if __name__ == "__main__":
    app.run(debug=True)
