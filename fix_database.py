import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Test connection first
def test_connection():
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT')
        )
        print("✅ Database connection successful!")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status='active'")
        count = cursor.fetchone()[0]
        print(f"📊 Current active jobs in database: {count}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

# Add sample jobs
def add_sample_jobs():
    if not test_connection():
        return
    
    sample_jobs = [
        {
            'title': 'Python Developer',
            'company': 'Tech Corp',
            'location': 'Remote',
            'description': 'We are looking for a skilled Python developer with experience in Flask, Django, and web development. Strong problem-solving skills required.',
            'requirements': 'Python, Flask, Django, SQL, Git, 3+ years experience'
        },
        {
            'title': 'Full Stack Developer',
            'company': 'StartupXYZ',
            'location': 'New York, NY',
            'description': 'Join our growing team as a full stack developer. Work with React, Node.js, and Python to build amazing products.',
            'requirements': 'React, Node.js, Python, JavaScript, HTML, CSS, MongoDB'
        },
        {
            'title': 'Data Scientist',
            'company': 'Data Analytics Inc',
            'location': 'San Francisco, CA',
            'description': 'Looking for a data scientist with machine learning expertise. Work on cutting-edge AI projects.',
            'requirements': 'Python, Machine Learning, Pandas, NumPy, Scikit-learn, TensorFlow'
        },
        {
            'title': 'Backend Developer',
            'company': 'CloudTech Solutions',
            'location': 'Remote',
            'description': 'Senior backend developer needed for microservices architecture. Experience with cloud platforms required.',
            'requirements': 'Python, Flask, Docker, Kubernetes, AWS, PostgreSQL, 5+ years experience'
        },
        {
            'title': 'Software Engineer',
            'company': 'Innovation Labs',
            'location': 'Austin, TX',
            'description': 'Software engineer position for developing scalable web applications. Great team environment.',
            'requirements': 'Python, JavaScript, React, SQL, Git, Agile methodology'
        }
    ]
    
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT')
        )
        
        cursor = conn.cursor()
        
        for job in sample_jobs:
            # Check if job already exists
            cursor.execute(
                "SELECT job_id FROM jobs WHERE title = %s AND company = %s",
                (job['title'], job['company'])
            )
            
            if cursor.fetchone() is None:  # Job doesn't exist, insert it
                cursor.execute("""
                    INSERT INTO jobs (employer_id, title, description, requirements, location, company,
                                    source, status, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    1,  # Default employer_id
                    job['title'],
                    job['description'],
                    job['requirements'],
                    job['location'],
                    job['company'],
                    'Manual',
                    'active',
                    True,
                    datetime.now()
                ))
                print(f"✅ Added job: {job['title']}")
            else:
                print(f"⚠️  Job already exists: {job['title']}")
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"🎉 Database setup completed!")
        
        # Test again
        test_connection()
        
    except Exception as e:
        print(f"❌ Error adding sample jobs: {e}")

if __name__ == "__main__":
    add_sample_jobs()
