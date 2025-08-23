import psycopg2, os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
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
        'description': 'We are looking for a skilled Python developer…',
        'requirements': 'Python, Flask, Django, SQL, Git, 3+ years experience'
    },
    # add the other 4 job dicts here…
]
for job in sample_jobs:
    cursor.execute(
        "SELECT job_id FROM jobs WHERE title=%s AND company=%s",
        (job['title'], job['company'])
    )
    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO jobs (
                employer_id, title, description, requirements, location,
                company, source, status, is_active, created_at
            ) VALUES (
                1, %s, %s, %s, %s, %s, 'Manual', 'active', TRUE, %s
            )
        """, (
            job['title'], job['description'], job['requirements'],
            job['location'], job['company'], datetime.now()
        ))
conn.commit()
cursor.close()
conn.close()
print("Sample jobs added.")
