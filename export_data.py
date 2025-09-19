# export_data.py
import psycopg2
import json
from datetime import datetime
import psycopg2.extras

DATABASE_URL = "postgresql://root_zjh6_user:dTpIeWW6y892QArn2I9XOZGZNLp3lwVN@dpg-d2io66ur433s73e19fm0-a.oregon-postgres.render.com:5432/root_zjh6"

def export_data():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Export users
    cursor.execute("SELECT user_id, email, first_name, last_name, user_type, created_at FROM users")
    users = cursor.fetchall()

    # Export resumes
    cursor.execute("SELECT * FROM resumes")
    resumes = cursor.fetchall()

    # Export recent jobs
    cursor.execute("SELECT * FROM jobs WHERE status='active' ORDER BY created_at DESC LIMIT 100")
    jobs = cursor.fetchall()

    backup = {
        "export_date": datetime.utcnow().isoformat(),
        "users": users,
        "resumes": resumes,
        "jobs": jobs
    }
    with open("database_backup.json", "w") as f:
        json.dump(backup, f, default=str, indent=2)

    cursor.close()
    conn.close()
    print(f"Exported {len(users)} users, {len(resumes)} resumes, {len(jobs)} jobs")

if __name__ == "__main__":
    export_data()
