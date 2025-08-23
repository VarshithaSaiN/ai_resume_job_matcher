import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

sample_jobs = [
    {
        'title': 'Python Developer',
        'company': 'Tech Corp',
        'location': 'Remote',
        'description': 'We are looking for a skilled Python developer with experience in Flask, Django, and web development. Strong problem-solving skills required.',
        'requirements': 'Python, Flask, Django, SQL, Git, 3+ years experience',
        'source': 'Manual',
        'status': 'active',
        'is_active': True
    },
    {
        'title': 'Full Stack Developer', 
        'company': 'StartupXYZ',
        'location': 'New York, NY',
        'description': 'Join our growing team as a full stack developer. Work with React, Node.js, and Python to build amazing products.',
        'requirements': 'React, Node.js, Python, JavaScript, HTML, CSS, MongoDB',
        'source': 'Manual',
        'status': 'active', 
        'is_active': True
    },
    {
        'title': 'Data Scientist',
        'company': 'Data Analytics Inc',
        'location': 'San Francisco, CA', 
        'description': 'Looking for a data scientist with machine learning expertise. Work on cutting-edge AI projects.',
        'requirements': 'Python, Machine Learning, Pandas, NumPy, Scikit-learn, TensorFlow',
        'source': 'Manual',
        'status': 'active',
        'is_active': True
    },
    {
        'title': 'Backend Developer',
        'company': 'CloudTech Solutions',
        'location': 'Remote',
        'description': 'Senior backend developer needed for microservices architecture. Experience with cloud platforms required.',
        'requirements': 'Python, Flask, Docker, Kubernetes, AWS, PostgreSQL, 5+ years experience',
        'source': 'Manual', 
        'status': 'active',
        'is_active': True
    },
    {
        'title': 'Software Engineer',
        'company': 'Innovation Labs', 
        'location': 'Austin, TX',
        'description': 'Software engineer position for developing scalable web applications. Great team environment.',
        'requirements': 'Python, JavaScript, React, SQL, Git, Agile methodology',
        'source': 'Manual',
        'status': 'active',
        'is_active': True
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
            job['source'],
            job['status'],
            job['is_active'],
            datetime.now()
        ))
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Successfully added {len(sample_jobs)} sample jobs!")
    
except Exception as e:
    print(f"❌ Error adding sample jobs: {e}")
