-- PostgreSQL Database Schema for AI Resume Matcher
-- Converted from MySQL to PostgreSQL

-- Create database
CREATE DATABASE root_zjh6;

-- Connect to the database

-- Users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    user_type VARCHAR(20) DEFAULT 'job_seeker' CHECK (user_type IN ('job_seeker', 'employer', 'admin')),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    reset_token VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create trigger for updated_at automatic update
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Resumes table
CREATE TABLE resumes (
    resume_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    file_path VARCHAR(500),
    original_filename VARCHAR(255),
    parsed_text TEXT,
    skills_extracted JSONB,
    experience_years INTEGER,
    education VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_resumes_user_id ON resumes(user_id);

-- Jobs table
CREATE TABLE jobs (
    job_id SERIAL PRIMARY KEY,
    employer_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    requirements TEXT,
    location VARCHAR(255),
    company VARCHAR(255) DEFAULT NULL,
    source VARCHAR(50) DEFAULT 'Manual',
    external_url TEXT DEFAULT NULL,
    url VARCHAR(800),
    salary_min DECIMAL(10,2),
    salary_max DECIMAL(10,2),
    employment_type VARCHAR(20) CHECK (employment_type IN ('full_time', 'part_time', 'contract', 'internship')),
    status VARCHAR(10) DEFAULT 'active' CHECK (status IN ('active', 'closed', 'draft')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_employer_id ON jobs(employer_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_external_url ON jobs(external_url);

-- Skills master table
CREATE TABLE skills (
    skill_id SERIAL PRIMARY KEY,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50),
    synonyms JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User skills mapping
CREATE TABLE user_skills (
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
    proficiency_level VARCHAR(20) CHECK (proficiency_level IN ('beginner', 'intermediate', 'advanced', 'expert')),
    years_experience INTEGER,
    PRIMARY KEY (user_id, skill_id)
);

-- Job matches table
CREATE TABLE job_matches (
    match_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    resume_id INTEGER REFERENCES resumes(resume_id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES jobs(job_id) ON DELETE CASCADE,
    match_score DECIMAL(5,2),
    skill_match_percentage DECIMAL(5,2),
    experience_match DECIMAL(5,2),
    education_match DECIMAL(5,2),
    score_breakdown JSONB DEFAULT NULL,
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_matches_match_score ON job_matches(match_score DESC);
CREATE INDEX idx_job_matches_resume_job ON job_matches(resume_id, job_id);

-- Job applications table
CREATE TABLE job_applications (
    application_id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(job_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    resume_id INTEGER REFERENCES resumes(resume_id) ON DELETE CASCADE,
    cover_letter TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'shortlisted', 'rejected', 'hired')),
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_applications_status ON job_applications(status);
CREATE INDEX idx_job_applications_applied_at ON job_applications(applied_at);

-- Sample queries to verify structure
SELECT * FROM jobs WHERE is_active = TRUE AND status = 'active';

-- Clean up queries for PostgreSQL
DELETE FROM jobs WHERE status != 'active' OR is_active = FALSE;

DELETE FROM jobs
WHERE LOWER(description) LIKE '%no longer accepting applications%'
OR LOWER(requirements) LIKE '%no longer accepting applications%'
OR LOWER(title) LIKE '%no longer accepting applications%'
OR LOWER(description) = 'no longer accepting applications'
OR LOWER(requirements) = 'no longer accepting applications'
OR LOWER(title) = 'no longer accepting applications';

DELETE FROM jobs WHERE status = 'closed';

-- Verify final structure
SELECT job_id, title, description, requirements
FROM jobs
WHERE LOWER(description) LIKE '%no longer accepting applications%'
OR LOWER(requirements) LIKE '%no longer accepting applications%'
OR LOWER(title) LIKE '%no longer accepting applications%'
OR LOWER(description) = 'no longer accepting applications'
OR LOWER(requirements) = 'no longer accepting applications'
OR LOWER(title) = 'no longer accepting applications';

SELECT * FROM jobs WHERE status = 'active' AND is_active = TRUE
AND description NOT LIKE '%No longer accepting applications%';
