# import_data.py
import psycopg2
import json

DATABASE_URL = "postgresql://ai_resume_job_matcher_v2_user:YxgrcyWMqKb7m0Y2IvTmURtaAOdoB2uj@dpg-d36gdbnfte5s73beqmng-a.singapore-postgres.render.com/ai_resume_job_matcher_v2"

def import_data():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    with open("database_backup.json") as f:
        backup = json.load(f)

    # Import users (adjust as needed; passwords must be reset)
    for u in backup["users"]:
        cursor.execute("""
            INSERT INTO users (user_id,email,first_name,last_name,user_type,created_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (email) DO NOTHING
        """, (u["user_id"], u["email"], u["first_name"], u["last_name"], u["user_type"], u["created_at"]))

    # Import resumes
    for r in backup["resumes"]:
        cursor.execute("""
            INSERT INTO resumes (resume_id,user_id,original_filename,parsed_text,created_at)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (resume_id) DO NOTHING
        """, (r["resume_id"], r["user_id"], r["original_filename"], r["parsed_text"], r["created_at"]))

    # Import jobs if desired (optional)
    for j in backup["jobs"]:
        cursor.execute("""
            INSERT INTO jobs (id,title,company,location,description,requirements,external_url,source,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (j["id"], j["title"], j["company"], j["location"], j["description"], j["requirements"], j["external_url"], j["source"], j["created_at"]))

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Data imported successfully!")

if __name__ == "__main__":
    import_data()
