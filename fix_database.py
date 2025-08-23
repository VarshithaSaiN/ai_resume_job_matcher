import psycopg2, os, json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()  # loads DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT from .env

def main():
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        port=os.environ['DB_PORT']
    )
    cursor = conn.cursor()

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

    # Insert sample jobs if they don't already exist
    for job in sample_jobs:
        cursor.execute(
            "SELECT job_id FROM jobs WHERE title=%s AND company=%s",
            (job['title'], job['company'])
        )
        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO jobs (
                    employer_id, title, description, requirements,
                    location, company, source, status, is_active, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                1,  # default employer
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
            print(f"Added job: {job['title']} at {job['company']}")
        else:
            print(f"Job already exists: {job['title']} at {job['company']}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Database population complete.")

if __name__ == "__main__":
    main()
