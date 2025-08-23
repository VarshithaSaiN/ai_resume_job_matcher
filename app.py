from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from job_fetcher.job_updater import JobUpdater
from job_fetcher.job_sources import JobAggregator
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
import spacy

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder="frontend/templates", static_folder='frontend/static')
app.secret_key = os.environ.get('SECRET_KEY', '1109')

# Upload config
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads/')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_FILE_SIZE', 16 * 1024 * 1024))

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'aijobmatcher@gmail.com'
app.config['MAIL_PASSWORD'] = 'uzih uzvu hdwv puzy'
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

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AI components with error handling
try:
    resume_parser = ResumeParser()
    job_matcher = JobMatcher()
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    logger.error(f"Error initializing AI components: {e}")
    resume_parser = None
    job_matcher = None
    nlp = None

# Initialize job updater and aggregator with error handling
try:
    job_updater = JobUpdater(DB_CONFIG)
    job_updater.update_jobs_for_keywords()
    job_aggregator = JobAggregator()
    # Start background updater
    job_updater.start_background_updater(update_interval_hours=6)
    atexit.register(job_updater.stop_background_updater)
except Exception as e:
    logger.error(f"Error initializing job updater: {e}")

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
            cursor.execute("SELECT COUNT(*) FROM users;")
            count = cursor.fetchone()
            cursor.close()
            conn.close()
            logger.info(f"Database connection successful. Users table has {count[0]} rows.")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

# Test database connection
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
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_login_history (user_id, login_time)
                VALUES (%s, %s)
            """, (user_id, datetime.now()))
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error tracking login: {e}")

def calculate_search_relevance(job, search_query):
    """Calculate relevance score"""
    if not search_query:
        return 100
    
    try:
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
    except Exception as e:
        logger.error(f"Error calculating search relevance: {e}")
        return 50

def get_filtered_jobs_for_user(user_skills, limit=50):
    """Get jobs filtered and matched for user skills with proper scoring"""
    if not user_skills:
        return []
    
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get active jobs (exclude manual jobs for better results)
        cursor.execute('''
            SELECT * FROM jobs 
            WHERE status='active' AND is_active=TRUE 
            AND source != 'Manual'
            AND description IS NOT NULL 
            AND requirements IS NOT NULL
            ORDER BY created_at DESC
        ''')
        
        jobs = cursor.fetchall()
        matched_jobs = []
        
        # Convert user skills to lowercase for better matching
        user_skills_lower = [skill.lower() for skill in user_skills]
        
        for job in jobs:
            # Create a combined text for skill matching
            job_text = f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}".lower()
            
            # Count skill matches
            skill_matches = 0
            matched_skills = []
            
            for skill in user_skills_lower:
                if skill in job_text:
                    skill_matches += 1
                    matched_skills.append(skill)
            
            # Calculate match score (percentage)
            if user_skills_lower:
                match_score = (skill_matches / len(user_skills_lower)) * 100
            else:
                match_score = 0
            
            # Only include jobs with at least 1 skill match
            if skill_matches > 0:
                job_dict = dict(job)
                job_dict['match_score'] = round(match_score, 1)
                job_dict['matched_skills'] = matched_skills
                job_dict['skill_matches'] = skill_matches
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
    try:
        if not user_skills:
            return 0
        job_text = f"{job.get('title','')} {job.get('description','')} {job.get('requirements','')}".lower()
        matches = sum(1 for skill in user_skills if skill.lower() in job_text)
        if len(user_skills) == 0:
            return 0
        return min((matches / len(user_skills)) * 100, 100)
    except Exception as e:
        logger.error(f"Error calculating resume job match: {e}")
        return 0

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        flash("An error occurred loading the homepage.", "danger")
        return "Error loading page", 500

@app.route('/test-jobs')
def test_jobs():
    try:
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
            html += f"<p><a href='/job_search_personalized'>Test Personalized Search</a></p>"
            return html
        
        return "Database connection failed"
    except Exception as e:
        logger.error(f"Error in test_jobs: {e}")
        return f"Error: {e}"

@app.route('/admin/statistics')
def admin_statistics():
    try:
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash("Access denied: Admins only.", "danger")
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        statistics = []
        
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
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
            cursor.close()
            conn.close()
        
        return render_template('admin_statistics.html', statistics=statistics)
    except Exception as e:
        logger.error(f"Error in admin_statistics: {e}")
        flash("Error fetching statistics.", "danger")
        return redirect(url_for('index'))

@app.route('/job_search_personalized')
def job_search_personalized():
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "danger")
            return redirect(url_for('dashboard'))
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get user's latest resume
        cursor.execute("""
            SELECT * FROM resumes 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session['user_id'],))
        
        resume = cursor.fetchone()
        user_skills = []
        
        if resume and resume.get('parsed_text'):
            try:
                parsed = json.loads(resume['parsed_text'])
                user_skills = parsed.get('skills', [])
            except (json.JSONDecodeError, KeyError):
                user_skills = []
        
        cursor.close()
        conn.close()
        
        # Get matching jobs
        if user_skills:
            jobs = get_filtered_jobs_for_user(user_skills, limit=50)
        else:
            jobs = []
        
        return render_template(
            'job_search_personalized.html',
            jobs=jobs,
            user_skills=user_skills,
            total_jobs=len(jobs)
        )
    except Exception as e:
        logger.error(f"Error in job_search_personalized: {e}")
        flash("Error loading personalized job search.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/search-jobs')
def search_jobs():
    try:
        query = request.args.get('q', '').strip()
        location = request.args.get('location', '').strip()
        source = request.args.get('source', '').strip()
        
        conn = get_db_connection()
        jobs = []
        total = 0
        
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Base query for active jobs excluding manual jobs and irrelevant search links
            base_query = """
                SELECT * FROM jobs 
                WHERE status = 'active' AND is_active = TRUE
                AND source != 'Manual'
                AND title NOT LIKE '%search%'
                AND (external_url IS NULL OR external_url NOT LIKE '%/jobs/search%')
            """
            params = []
            
            # Add search filters if provided
            if query:
                base_query += " AND (title ILIKE %s OR description ILIKE %s OR company ILIKE %s)"
                like_pattern = f"%{query}%"
                params.extend([like_pattern, like_pattern, like_pattern])
                
            if location:
                base_query += " AND location ILIKE %s"
                params.append(f"%{location}%")
                
            if source:
                base_query += " AND source = %s"
                params.append(source)
                
            base_query += " ORDER BY created_at DESC LIMIT 50"
            
            if params:
                cursor.execute(base_query, params)
            else:
                cursor.execute(base_query)
            jobs = cursor.fetchall()
            total = len(jobs)
            logger.info(f"Found {total} jobs for query: '{query}'")
            
            cursor.close()
            conn.close()
        else:
            flash("Database connection error.", "danger")
        
        return render_template('job_search.html',
                               jobs=jobs,
                               total=total,
                               query=query,
                               location=location,
                               source=source)
    except Exception as e:
        logger.error(f"Error in search_jobs: {e}")
        flash("Error searching jobs. Please try again.", "danger")
        return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
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
    except Exception as e:
        logger.error(f"Error in register: {e}")
        flash("Registration error. Please try again.", "danger")
        return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
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
                    
                    # Track login for statistics
                    track_user_login(user['user_id'])
                    
                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard'))
                else:
                    flash("Incorrect password.", "danger")
            else:
                flash("Database connection error.", "danger")
        
        return render_template('login.html')
    except Exception as e:
        logger.error(f"Error in login: {e}")
        flash("Login error. Please try again.", "danger")
        return render_template('login.html')

@app.route('/logout')
def logout():
    try:
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error in logout: {e}")
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
                AND description NOT LIKE '%no longer accepting applications%'
                AND requirements NOT LIKE '%no longer accepting applications%'
                AND title NOT LIKE '%no longer accepting applications%'
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

        # Get matching jobs if user has skills
        if user_skills:
            job_list = get_filtered_jobs_for_user(user_skills)
            matching_jobs_count = len(job_list)

            if job_list:
                best_match_score = max(job.get('match_score', 0) for job in job_list)
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
    try:
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
                
                file.save(filepath)
                
                if resume_parser:
                    parsed_text = resume_parser.parse_resume(filepath)
                else:
                    parsed_text = {"error": "Resume parser not available"}
                    
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
            else:
                flash("Invalid file type. Only PDF and DOCX allowed.", "danger")

        return render_template('upload_resume.html', parsed_text=parsed_text, existing_resumes=existing_resumes)
    except Exception as e:
        logger.error(f"Error in upload_resume: {e}")
        flash("Error uploading resume. Please try again.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/post_job', methods=['GET', 'POST'])
def post_job():
    try:
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
    except Exception as e:
        logger.error(f"Error in post_job: {e}")
        flash("Error posting job. Please try again.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/match_jobs/<resume_id>')
def match_jobs(resume_id):
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "danger")
            return redirect(url_for('dashboard'))
        
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get the specific resume
        cursor.execute("SELECT * FROM resumes WHERE resume_id = %s AND user_id = %s", 
                      (resume_id, session['user_id']))
        resume = cursor.fetchone()
        
        if not resume:
            flash("Resume not found", "danger")
            return redirect(url_for('dashboard'))
        
        # Extract skills from resume
        user_skills = []
        if resume.get('parsed_text'):
            try:
                parsed = json.loads(resume['parsed_text'])
                user_skills = parsed.get('skills', [])
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Get ONLY personalized/matched jobs (not all jobs)
        if user_skills:
            jobs = get_filtered_jobs_for_user(user_skills, limit=100)
            
            # Further enhance matching using the job matcher
            enhanced_jobs = []
            for job in jobs:
                try:
                    # Use the job matcher for detailed scoring
                    if job_matcher:
                        match_result = job_matcher.calculate_match_score(
                            resume['parsed_text'] if isinstance(resume['parsed_text'], str) else json.dumps(resume['parsed_text']),
                            job.get('description', ''),
                            job.get('requirements', '')
                        )
                        
                        job_dict = dict(job)
                        job_dict['detailed_match_score'] = match_result['final_score']
                        job_dict['skills_breakdown'] = match_result
                        enhanced_jobs.append(job_dict)
                    else:
                        enhanced_jobs.append(dict(job))
                        
                except Exception as e:
                    # If detailed matching fails, keep the basic match score
                    enhanced_jobs.append(dict(job))
            
            # Sort by detailed match score if available, otherwise by basic match score
            enhanced_jobs.sort(key=lambda x: x.get('detailed_match_score', x.get('match_score', 0)), reverse=True)
            jobs = enhanced_jobs
        else:
            jobs = []
        
        cursor.close()
        conn.close()
        
        return render_template(
            'job_matches.html',
            jobs=jobs,
            resume=resume,
            user_skills=user_skills,
            total_matches=len(jobs)
        )
        
    except Exception as e:
        logger.error(f"Error in match_jobs: {e}")
        flash("Error processing job matches", "danger")
        return redirect(url_for('dashboard'))

@app.route('/admin/cleanup-closed-jobs', methods=['POST'])
def cleanup_closed_jobs():
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))

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
        logger.error(f"Error in cleanup_closed_jobs: {e}")
        flash(f"Cleanup failed: {e}", "danger")

    return redirect(url_for('dashboard'))

@app.route('/admin/cleanup_jobs', methods=['POST'])
def cleanup_jobs():
    try:
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash("Access denied.", "danger")
            return redirect(url_for('login'))
        
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
        logger.error(f"Error in cleanup_jobs: {e}")
        flash(f"Cleanup failed: {e}", "danger")
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/cleanup_manual_jobs', methods=['POST'])
def cleanup_manual_jobs():
    try:
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash("Access denied.", "danger")
            return redirect(url_for('login'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM jobs WHERE source = 'Manual'")
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"{deleted_count} manual jobs removed.", "success")
    except Exception as e:
        logger.error(f"Error in cleanup_manual_jobs: {e}")
        flash(f"Cleanup failed: {e}", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
def admin_dashboard():
    try:
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash("Access denied: Admins only.", "danger")
            return redirect(url_for('login'))
        return render_template('admin_dashboard.html')
    except Exception as e:
        logger.error(f"Error in admin_dashboard: {e}")
        flash("Error loading admin dashboard.", "danger")
        return redirect(url_for('index'))

@app.route('/delete_resume/<int:resume_id>', methods=['POST'])
def delete_resume(resume_id):
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))
            
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
        logger.error(f"Error in delete_resume: {e}")
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for('dashboard'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    try:
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
    except Exception as e:
        logger.error(f"Error in forgot_password: {e}")
        flash("Error processing password reset.", "danger")
        return render_template('forgot_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    try:
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
    except Exception as e:
        logger.error(f"Error in reset_password: {e}")
        flash("Error resetting password.", "danger")
        return redirect(url_for('login'))

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    try:
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
    except Exception as e:
        logger.error(f"Error in reset_password_token: {e}")
        flash("Error processing password reset.", "danger")
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
