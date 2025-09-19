from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from job_fetcher.job_updater import JobUpdater
from job_fetcher.job_sources import JobAggregator
from utils import strip_html_tags
from flask import send_from_directory
import psycopg2
from psycopg2 import Error
import psycopg2.extras
import os
import json
from datetime import datetime
import uuid
from urllib.parse import urlencode
import atexit
import threading
import time
import logging
import secrets
from ai_engine.resume_parser import ResumeParser
from ai_engine.job_matcher import JobMatcher
from flask_mail import Mail, Message
# import spacy
# nlp = spacy.load("en_core_web_sm")
from dotenv import load_dotenv
load_dotenv()  # This loads your .env file

# Initialize Flask app
app = Flask(__name__, template_folder="frontend/templates", static_folder='frontend/static')
app.secret_key = '1109'  # Change this in production

# Upload config
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'aijobmatcher@gmail.com'
app.config['MAIL_PASSWORD'] = 'uzih uzvu hdwv puzy'  # Your actual app password
app.config['MAIL_DEFAULT_SENDER'] = 'aijobmatcher@gmail.com'
mail = Mail(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database config
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'dpg-d2io66ur433s73e19fm0-a'),
    'database': os.environ.get('DB_NAME', 'root_zjh6'),
    'user': os.environ.get('DB_USER', 'root_zjh6_user'),
    'password': os.environ.get('DB_PASSWORD', 'dTpIeWW6y892QArn2I9XOZGZNLp3lwVN'),
    'port': os.environ.get('DB_PORT', '5432')
}

# Initialize AI components
resume_parser = ResumeParser()
job_matcher = JobMatcher()

# Initialize job updater and aggregator
job_updater = JobUpdater(DB_CONFIG)
job_updater.update_jobs_for_keywords()
job_aggregator = JobAggregator()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Start background updater
job_updater.start_background_updater(update_interval_hours=6)
atexit.register(job_updater.stop_background_updater)

def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"Error connecting to DB: {e}")
        return None
def test_database_connection():
    """Test database connection and verify tables exist"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            # Test if users table exists
            cursor.execute("SELECT COUNT(*) FROM users;")
            count = cursor.fetchone()
            cursor.close()
            conn.close()
            logger.info(f"Database connection successful. Users table has {count[0]} rows.")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

# Add this before your app routes
if not test_database_connection():
    logger.error("Database connection failed. Please check your database setup.")

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_job_accepting_applications(job):
    """Check if job is still accepting applications"""
    text_to_check = f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}".lower()
    inactive_phrases = [
        'no longer accepting applications',
        'position filled',
        'applications closed',
        'hiring closed',
        'position closed',
        'job closed',
        'hiring complete'
    ]
    for phrase in inactive_phrases:
        if phrase in text_to_check:
            return False
    return True
def track_user_login(user_id):
    """Track user login for statistics"""
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO user_login_history (user_id, login_time)
                VALUES (%s, %s)
            """, (user_id, datetime.now()))
            conn.commit()
        except Exception as e:
            logger.error(f"Error tracking login: {e}")
        finally:
            cursor.close()
            conn.close()
import re
from html import unescape

def clean_html_description(description):
    """Remove HTML tags and decode HTML entities from job description"""
    if not description:
        return ""
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', description)
    # Decode HTML entities like &amp; &lt; &gt;
    clean = unescape(clean)
    # Remove extra whitespace
    clean = ' '.join(clean.split())
    # Limit length for display
    return clean[:500] + "..." if len(clean) > 500 else clean
def calculate_realistic_match_score(job, user_skills):
    """Calculate realistic match score based on actual skill overlap"""
    if not user_skills:
        return 0
    
    try:
        # Combine job text for analysis
        job_text = f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}".lower()
        
        # Convert skills to lowercase for matching
        user_skills_lower = [skill.lower().strip() for skill in user_skills]
        
        # Find matching skills
        matched_skills = []
        for skill in user_skills_lower:
            if skill in job_text and len(skill) > 2:  # Avoid matching very short words
                matched_skills.append(skill)
        
        # Calculate percentage based on matched skills
        if len(user_skills_lower) == 0:
            return 0
            
        base_score = (len(matched_skills) / len(user_skills_lower)) * 100
        
        # Add bonus for exact title matches
        title_lower = job.get('title', '').lower()
        title_bonus = 0
        for skill in user_skills_lower:
            if skill in title_lower:
                title_bonus += 5  # 5% bonus per skill in title
        
        # Add bonus for company/role relevance
        relevance_bonus = 0
        tech_keywords = ['developer', 'engineer', 'programmer', 'analyst', 'manager', 'scientist']
        for keyword in tech_keywords:
            if keyword in title_lower:
                relevance_bonus += 2
        
        # Final score calculation
        final_score = min(base_score + title_bonus + relevance_bonus, 100)
        
        # Ensure minimum realistic scores
        if matched_skills and final_score < 10:
            final_score = 10 + (len(matched_skills) * 5)
        
        return round(final_score, 1)
        
    except Exception as e:
        logger.error(f"Error calculating match score: {e}")
        return 0
from flask import send_from_directory

@app.route("/init-database")
def init_database():
    try:
        with open("schema.sql") as f:
            schema_sql = f.read()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(schema_sql)
        conn.commit()
        cur.close()
        conn.close()
        return "✅ Database initialized!"
    except Exception as e:
        return f"❌ Initialization error: {e}"
# Add these imports if not already present
from flask import send_from_directory
@app.route('/google85221926df2ad0e3.html')
def google_verification():
    return send_from_directory('static', 'google85221926df2ad0e3.html')
# Add these routes anywhere in your app.py file
@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')

@app.route('/debug-jobs')
def debug_jobs():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT COUNT(*) as total FROM jobs")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM jobs WHERE status='active' AND is_active=TRUE")
        active = cursor.fetchone()['active']
        
        cursor.execute("SELECT COUNT(*) as non_manual FROM jobs WHERE source != 'Manual' AND status='active'")
        non_manual = cursor.fetchone()['non_manual']
        
        cursor.close()
        conn.close()
        
        return f"Total jobs: {total}, Active: {active}, Non-manual: {non_manual}"
    return "Database connection failed"

@app.route('/personalized-search')
def personalized_search_redirect():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT resume_id FROM resumes
            WHERE user_id=%s
            ORDER BY created_at DESC
            LIMIT 1
        """, (session['user_id'],))
        resume = cursor.fetchone()
        cursor.close()
        conn.close()
        if resume:
            return redirect(url_for('match_jobs', resume_id=resume['resume_id']))
    flash("Please upload a resume first to get personalized matches.", "warning")
    return redirect(url_for('upload_resume'))
@app.route('/test-jobs')
def test_jobs():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT COUNT(*) as count FROM jobs WHERE status='active' AND is_active=TRUE")
        job_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT title, company, location FROM jobs WHERE status='active' AND is_active=TRUE LIMIT 10")
        jobs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        html = f"<h2>Database Test Results</h2>"
        html += f"<p><strong>Total active jobs:</strong> {job_count}</p>"
        html += f"<h3>Sample Jobs:</h3><ul>"
        for job in jobs:
            html += f"<li>{job['title']} at {job['company']} - {job['location']}</li>"
        html += "</ul>"
        html += f"<p><a href='/search-jobs'>Test Job Search</a></p>"
        html += f"<p><a href='/jobs/search-personalized'>Test Personalized Search</a></p>"
        return html
    
    return "Database connection failed"

@app.route('/admin/statistics')
def admin_statistics():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    statistics = []
    
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get user statistics with login count and resume count
            cursor.execute("""
                SELECT 
                    u.user_id,
                    u.email,
                    u.first_name,
                    u.last_name,
                    u.created_at as registration_date,
                    COALESCE(login_stats.login_count, 0) as login_count,
                    COALESCE(resume_stats.resume_count, 0) as resume_count
                FROM users u
                LEFT JOIN (
                    SELECT user_id, COUNT(*) as login_count
                    FROM user_login_history 
                    GROUP BY user_id
                ) login_stats ON u.user_id = login_stats.user_id
                LEFT JOIN (
                    SELECT user_id, COUNT(*) as resume_count
                    FROM resumes 
                    GROUP BY user_id
                ) resume_stats ON u.user_id = resume_stats.user_id
                WHERE u.user_type != 'admin'
                ORDER BY u.created_at DESC
            """)
            
            statistics = cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error fetching admin statistics: {e}")
            flash(f"Error fetching statistics: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('admin_statistics.html', statistics=statistics)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/jobs/search-personalized')
def calculate_search_relevance(job, search_query):
    """Calculate relevance score"""
    if not search_query:
        return 100
    job_text = f"{job.get('title','')} {job.get('description','')} {job.get('requirements','')} {job.get('company','')}".lower()
    search_lower = search_query.lower()
    relevance_score = 0

    if search_lower in job.get('title','').lower():
        relevance_score += 50

    search_words = [word.strip() for word in search_lower.split() if len(word.strip()) > 2]
    title_lower = job.get('title','').lower()
    for word in search_words:
        if word in title_lower:
            relevance_score += 10

    description_matches = sum(1 for word in search_words if word in job_text)
    relevance_score += min(description_matches * 5, 30)

    if search_lower in job.get('company','').lower():
        relevance_score += 20

    tech_keywords = ['python', 'javascript', 'react', 'node', 'java', 'sql', 'aws', 'docker',
                    'kubernetes', 'machine learning', 'data science', 'ai', 'frontend', 'backend',
                    'full stack', 'devops']
    search_tech_words = [word for word in search_words if word in tech_keywords]

    for tech_word in search_tech_words:
        if tech_word in job_text:
            relevance_score += 15

    return min(relevance_score, 100)
def get_filtered_jobs_for_user(user_skills, search_query="", location_filter="", limit=50):
    """Get jobs filtered and matched for user skills with proper scoring"""
    if not user_skills:
        return []
    
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        base_query = """
            SELECT * FROM jobs 
            WHERE status='active' AND is_active=TRUE 
            AND source != 'Manual'
            AND description IS NOT NULL 
            AND requirements IS NOT NULL
        """
        params = []

        # Apply search filters
        if search_query:
            base_query += " AND (title ILIKE %s OR description ILIKE %s OR company ILIKE %s)"
            like_pattern = f"%{search_query}%"
            params.extend([like_pattern, like_pattern, like_pattern])
            
        if location_filter:
            base_query += " AND location ILIKE %s"
            params.append(f"%{location_filter}%")

        base_query += " ORDER BY created_at DESC"
        
        cursor.execute(base_query, params)
        jobs = cursor.fetchall()
        matched_jobs = []
        
        user_skills_lower = [skill.lower() for skill in user_skills]
        
        for job in jobs:
            job_text = f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}".lower()
            
            # Find matching skills
            matched_skills = []
            for skill in user_skills_lower:
                if skill in job_text and len(skill) > 2:
                    matched_skills.append(skill)
            
            # Only include jobs with at least 1 skill match
            if matched_skills:
                # Calculate realistic match score
                match_score = calculate_realistic_match_score(job, user_skills)
                
                job_dict = dict(job)
                job_dict['match_score'] = match_score
                job_dict['matched_skills'] = matched_skills
                job_dict['skill_matches'] = len(matched_skills)
                matched_jobs.append(job_dict)
        
        # Sort by match score (highest first)
        matched_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        
        cursor.close()
        conn.close()
        return matched_jobs[:limit]
        
    except Exception as e:
        logger.error(f"Error in get_filtered_jobs_for_user: {e}")
        return []

def calculate_resume_job_match(job, user_skills):
    """Calculate skills-based match score"""
    if not user_skills:
        return 0
    job_text = f"{job.get('title','')} {job.get('description','')} {job.get('requirements','')}".lower()
    matches = sum(1 for skill in user_skills if skill.lower() in job_text)
    if len(user_skills) == 0:
        return 0
    return min((matches / len(user_skills)) * 100, 100)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        user_type = request.form.get('user_type', 'job_seeker')

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash("Email already registered. Please use a different one.", "danger")
                conn.close()
                return redirect(url_for('register'))

            cursor.execute(
                "INSERT INTO users (first_name, last_name, email, password, user_type, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (first_name, last_name, email, hashed_password, user_type, datetime.now())
            )
            conn.commit()
            conn.close()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("Database connection error.", "danger")

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                flash("Email not found. Please register first.", "danger")
            elif check_password_hash(user['password'], password):
                session['user_id'] = user['user_id']
                session['user_name'] = user['first_name']
                session['user_type'] = user['user_type']
                
                # Track login for statistics - NEW LINE
                track_user_login(user['user_id'])
                
                flash("Login successful!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Incorrect password.", "danger")
        else:
            flash("Database connection error.", "danger")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))

        resumes = []
        all_jobs_count = 0
        matching_jobs_count = 0
        best_match_score = 0.0
        user_skills = []
        job_list = []

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Fetch all resumes
            cursor.execute("SELECT * FROM resumes WHERE user_id = %s", (session['user_id'],))
            resumes = cursor.fetchall()

            # Get total count of ALL active jobs
            cursor.execute('''
                SELECT COUNT(*) as total_count FROM jobs 
                WHERE status = 'active' AND is_active = TRUE
                AND source != 'Manual'
                AND description IS NOT NULL
            ''')
            result = cursor.fetchone()
            all_jobs_count = result['total_count'] if result else 0

            # Fetch latest resume to get skills
            cursor.execute("SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (session['user_id'],))
            resume = cursor.fetchone()

            if resume and resume.get('parsed_text'):
                try:
                    parsed = json.loads(resume['parsed_text'])
                    user_skills = parsed.get('skills', [])
                except (json.JSONDecodeError, KeyError):
                    user_skills = []

            cursor.close()
            conn.close()

        # Get matching jobs if user has skills - USE SAME LOGIC AS JOB MATCHES
        if user_skills:
            job_list = get_filtered_jobs_for_user(user_skills)
            matching_jobs_count = len(job_list)

            # Calculate best match using the SAME logic as job matches
            if job_list:
                # Apply the same scoring logic
                enhanced_jobs = []
                for job in job_list:
                    # Use the realistic match score calculation
                    match_score = calculate_realistic_match_score(job, user_skills)
                    
                    # Enhanced scoring with JobMatcher if available
                    detailed_score = match_score
                    if job_matcher:
                        try:
                            result = job_matcher.calculate_match_score(
                                resume['parsed_text'],
                                job.get('description', ''),
                                job.get('requirements', '')
                            )
                            detailed_score = result.get('final_score', match_score)
                        except Exception:
                            pass
                    
                    enhanced_jobs.append({
                        'job': job,
                        'detailed_match_score': detailed_score
                    })
                
                # Get the highest detailed match score
                best_match_score = max(job.get('detailed_match_score', 0) for job in enhanced_jobs)
            else:
                best_match_score = 0
        else:
            job_list = []
            matching_jobs_count = 0
            best_match_score = 0
            
        return render_template(
            'dashboard.html',
            resumes=resumes,
            job_count=all_jobs_count,
            matching_jobs_count=matching_jobs_count,
            best_match_score=best_match_score,
            jobs=job_list,
            user_skills=user_skills
        )
    except Exception as e:
        logger.error(f"Error in dashboard: {e}")
        flash("Error loading dashboard.", "danger")
        return redirect(url_for('index'))


@app.route('/upload_resume', methods=['GET', 'POST'])
def upload_resume():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    parsed_text = None
    existing_resumes = []

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
        existing_resumes = cursor.fetchall()
        cursor.close()
        conn.close()

    if request.method == 'POST':
        if 'resume_file' not in request.files:
            flash("No file part.", "danger")
            return redirect(request.url)

        file = request.files['resume_file']
        if file.filename == '':
            flash("No selected file.", "danger")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            try:
                file.save(filepath)
                parsed_text = resume_parser.parse_resume(filepath)
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    # Avoid duplicate uploads by file name
                    cursor.execute("SELECT * FROM resumes WHERE user_id=%s AND original_filename=%s", (session['user_id'], filename))
                    duplicate = cursor.fetchone()
                    if duplicate:
                        flash("You have already uploaded this resume.", "warning")
                    else:
                        cursor.execute(
                            "INSERT INTO resumes (user_id, original_filename, file_path, parsed_text, created_at) VALUES (%s,%s,%s,%s,%s)",
                            (session['user_id'], filename, unique_name, json.dumps(parsed_text), datetime.now())
                        )
                        conn.commit()
                        flash("Resume uploaded and parsed successfully!", "success")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f"Error uploading file: {e}", "danger")
        else:
            flash("Invalid file type. Only PDF and DOCX allowed.", "danger")

    return render_template('upload_resume.html', parsed_text=parsed_text, existing_resumes=existing_resumes)
@app.route('/jobs/search')
def jobs_search():
    """General job search route"""
    search_query = request.args.get('keywords', '').strip()
    location_filter = request.args.get('location', '').strip()
    source_filter = request.args.get('source', '').strip()
    
    # Get jobs without user skills filter for general search
    jobs = get_filtered_jobs_for_user([], search_query, location_filter, source_filter)
    
    # Add search relevance scoring for general search
    for job in jobs:
        job['relevance_score'] = calculate_search_relevance(job, search_query)
    
    # Sort by relevance for general search
    jobs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    return render_template('job_search.html', 
                         jobs=jobs, 
                         search_query=search_query,
                         location_filter=location_filter,
                         source_filter=source_filter)

@app.route('/jobs/search-personalized')
def personalized_jobs_search():
    """Personalized job search route"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search_query = request.args.get('keywords', '').strip()
    location_filter = request.args.get('location', '').strip()
    source_filter = request.args.get('source', '').strip()
    
    # Get user skills
    user_skills = []
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", 
                      (session['user_id'],))
        resume = cursor.fetchone()
        if resume and resume.get('parsed_text'):
            try:
                parsed = json.loads(resume['parsed_text'])
                user_skills = parsed.get('skills', [])
            except (json.JSONDecodeError, KeyError):
                user_skills = []
        cursor.close()
        conn.close()
    
    # Get personalized jobs
    jobs = get_filtered_jobs_for_user(user_skills, search_query, location_filter, source_filter)
    
    return render_template('job_search_personalized.html', 
                         jobs=jobs, 
                         user_skills=user_skills,
                         search_query=search_query,
                         location_filter=location_filter,
                         source_filter=source_filter)

@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or session.get('user_type') != 'employer':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        location = request.form['location']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO jobs (employer_id, title, description, requirements, location, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (session['user_id'], title, description, requirements, location, datetime.now())
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash("Job posted successfully!", "success")
            return redirect(url_for('dashboard'))

    return render_template('post_job.html')
@app.route('/match_jobs/<int:resume_id>')
def match_jobs(resume_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get search parameters
    search_query = request.args.get('q', '').strip()
    location_filter = request.args.get('location', '').strip()

    conn = get_db_connection()
    matches = []  # Initialize matches here

    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT parsed_text FROM resumes WHERE resume_id=%s AND user_id=%s",
            (resume_id, session['user_id'])
        )
        resume = cursor.fetchone()

        if resume and resume.get('parsed_text'):
            try:
                skills = json.loads(resume['parsed_text']).get('skills', [])
            except json.JSONDecodeError:
                skills = []

            # Get personalized matches with search filters
            basic_jobs = get_filtered_jobs_for_user(skills, search_query, location_filter, limit=100)

            # Calculate proper match scores
            for job in basic_jobs:
                if job.get('source') == 'Manual':
                    continue

                # Calculate realistic match score based on skills
                match_score = calculate_realistic_match_score(job, skills)
                
                # Enhanced scoring with JobMatcher if available
                detailed_score = match_score
                if job_matcher:
                    try:
                        result = job_matcher.calculate_match_score(
                            resume['parsed_text'],
                            job.get('description', ''),
                            job.get('requirements', '')
                        )
                        detailed_score = result.get('final_score', match_score)
                    except Exception as e:
                        logger.error(f"JobMatcher error: {e}")

                matches.append({
                    "job": job,
                    "match_score": match_score,
                    "detailed_match_score": detailed_score,
                    "matched_skills": job.get('matched_skills', [])
                })

        cursor.close()
        conn.close()

    # Clean HTML descriptions AFTER matches is populated
    for match in matches:
        if match["job"].get('description'):
            match["job"]['description'] = clean_html_description(match["job"]['description'])
        if match["job"].get('requirements'):
            match["job"]['requirements'] = clean_html_description(match["job"]['requirements'])

    # Sort by detailed match score (descending order)
    matches.sort(key=lambda x: x.get('detailed_match_score', 0), reverse=True)

    return render_template('job_matches.html',
                         matches=matches,
                         resume_id=resume_id,
                         search_query=search_query,
                         location_filter=location_filter,
                         total_matches=len(matches))

@app.route('/search-jobs')
def search_jobs():
    query = request.args.get('q', '').strip()
    location = request.args.get('location', '').strip()
    
    conn = get_db_connection()
    jobs = []
    total = 0
    user_resume_id = None
    
    if conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get user's latest resume ID if logged in
        if 'user_id' in session:
            try:
                cursor.execute("""
                    SELECT resume_id FROM resumes 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (session['user_id'],))
                resume_row = cursor.fetchone()
                if resume_row:
                    user_resume_id = resume_row['resume_id']
            except Exception as e:
                logger.error(f"Error getting user resume: {e}")

        # Base query - make it less restrictive
        base_query = """
            SELECT * FROM jobs 
            WHERE status = 'active' 
            AND is_active = TRUE 
            AND source != 'Manual'
            AND description IS NOT NULL
        """
        params = []

        # Add search filters only if provided
        if query:
            base_query += " AND (title ILIKE %s OR description ILIKE %s OR company ILIKE %s)"
            like_pattern = f"%{query}%"
            params.extend([like_pattern, like_pattern, like_pattern])
            
        if location:
            base_query += " AND location ILIKE %s"
            params.append(f"%{location}%")
            
        base_query += " ORDER BY created_at DESC LIMIT 50"

        try:
            cursor.execute(base_query, params)
            jobs = cursor.fetchall()
            
            # Clean HTML from descriptions
            for job in jobs:
                if job.get('description'):
                    job['description'] = clean_html_description(job['description'])
            
            total = len(jobs)
            logger.info(f"Found {total} jobs for query: '{query}', location: '{location}'")
            
        except Exception as e:
            logger.error(f"Error searching jobs: {e}")
            flash("Error searching jobs. Please try again.", "danger")
        finally:
            cursor.close()
            conn.close()
    else:
        flash("Database connection error.", "danger")

    return render_template('job_search.html',
                         jobs=jobs,
                         total=total,
                         query=query,
                         location=location,
                         user_resume_id=user_resume_id)
@app.route('/admin/cleanup-closed-jobs', methods=['POST'])
def cleanup_closed_jobs():
    """Admin route to clean up jobs no longer accepting applications"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM jobs
                WHERE description LIKE '%No longer accepting applications%'
                OR title LIKE '%No longer accepting applications%'
                OR requirements LIKE '%No longer accepting applications%'
                OR description LIKE '%Position filled%'
                OR description LIKE '%Applications closed%'
                OR description LIKE '%Hiring closed%'
                OR description LIKE '%Position closed%'
                OR description LIKE '%Job closed%'
                OR description LIKE '%Hiring complete%'
            """)
            deleted_count = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            flash(f"Cleaned up {deleted_count} closed jobs successfully!", "success")
        else:
            flash("Database connection failed", "danger")

    except Exception as e:
        flash(f"Cleanup failed: {e}", "danger")

    return redirect(url_for('dashboard'))

@app.route('/admin/cleanup_jobs', methods=['POST'])
def cleanup_jobs():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM jobs 
            WHERE status = 'closed' OR is_active = FALSE
            OR description LIKE '%No longer accepting applications%'
            OR description LIKE '%Position filled%'
            OR description LIKE '%Applications closed%'
            OR description LIKE '%Hiring closed%'
            OR description LIKE '%Position closed%'
            OR description LIKE '%Job closed%'
            OR description LIKE '%Hiring complete%'
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        flash(f"{deleted_count} old/closed jobs cleaned up.", "success")
    except Exception as e:
        flash(f"Cleanup failed: {e}", "danger")
    
    return redirect(url_for('admin_dashboard'))
@app.route('/admin/cleanup_manual_jobs', methods=['POST'])
def cleanup_manual_jobs():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM jobs WHERE source = 'Manual'")
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"{deleted_count} manual jobs removed.", "success")
    except Exception as e:
        flash(f"Cleanup failed: {e}", "danger")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'admin':
        flash("Access denied: Admins only.", "danger")
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')
@app.route('/delete_resume/<int:resume_id>', methods=['POST'])
def delete_resume(resume_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT file_path FROM resumes WHERE resume_id=%s AND user_id=%s", (resume_id, session['user_id']))
            resume = cursor.fetchone()
            if resume and resume.get('file_path'):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], resume['file_path'])
                cursor.execute("DELETE FROM resumes WHERE resume_id=%s AND user_id=%s", (resume_id, session['user_id']))
                conn.commit()
                cursor.close()
                conn.close()
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as ex:
                        flash(f"Resume deleted from DB but file error: {ex}", "warning")
                flash("Resume deleted successfully!", "success")
            else:
                flash("Resume not found.", "danger")
        else:
            flash("Database connection error.", "danger")
    except Exception as e:
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for('dashboard'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash("Please enter your email.", "danger")
            return render_template('forgot_password.html')
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user:
                reset_token = secrets.token_urlsafe(32)
                cursor.execute("UPDATE users SET reset_token=%s WHERE email=%s", (reset_token, email))
                conn.commit()
                reset_url = url_for('reset_password_token', token=reset_token, _external=True)
                msg = Message(
                    "Password Reset Request",
                    sender=app.config['MAIL_USERNAME'],
                    recipients=[email]
                )
                msg.body = f"Hello,\n\nClick the link below to reset your password:\n{reset_url}\n\nIf you did not request this, ignore this email."
                mail.send(msg)
                flash("Reset link sent to your email.", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('login'))
            else:
                flash("Email not found.", "danger")
                cursor.close()
                conn.close()
        else:
            flash("Database connection error.", "danger")
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    if not email or not password:
        flash("Please enter both email and new password.", "danger")
        return render_template('reset_password.html', email=email)
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        hashed_password = generate_password_hash(password)
        cursor.execute("UPDATE users SET password=%s WHERE email=%s", (hashed_password, email))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Password reset successful! You can now log in.", "success")
        return redirect(url_for('login'))
    else:
        flash("Database connection error.", "danger")
        return render_template('reset_password.html', email=email)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT email FROM users WHERE reset_token=%s", (token,))
    user = cursor.fetchone()
    if not user:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('login'))
    email = user['email']
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        if not password:
            flash("Please enter a new password.", "danger")
            return render_template('reset_password.html', email=email, token=token)
        hashed_password = generate_password_hash(password)
        cursor.execute("UPDATE users SET password=%s, reset_token=NULL WHERE email=%s", (hashed_password, email))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Password reset successful! Please log in.", "success")
        return redirect(url_for('login'))
    cursor.close()
    conn.close()
    return render_template('reset_password.html', email=email, token=token)

if __name__ == '__main__':
    app.run(debug=True)
