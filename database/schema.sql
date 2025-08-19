CREATE DATABASE ai_resume_matcher;
USE ai_resume_matcher;

-- AI Resume & Job Matcher Database Schema
-- MySQL Database

-- Users table
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    user_type ENUM('job_seeker', 'employer', 'admin') DEFAULT 'job_seeker',
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Resumes table
CREATE TABLE resumes (
    resume_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    file_path VARCHAR(500),
    original_filename VARCHAR(255),
    parsed_text TEXT,
    skills_extracted JSON,
    experience_years INT,
    education VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
);

-- Jobs table
CREATE TABLE jobs (
    job_id INT PRIMARY KEY AUTO_INCREMENT,
    employer_id INT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    requirements TEXT,
    location VARCHAR(255),
    salary_min DECIMAL(10,2),
    salary_max DECIMAL(10,2),
    employment_type ENUM('full_time', 'part_time', 'contract', 'internship'),
    status ENUM('active', 'closed', 'draft') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_employer_id (employer_id),
    INDEX idx_status (status)
);

-- Skills master table
CREATE TABLE skills (
    skill_id INT PRIMARY KEY AUTO_INCREMENT,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50),
    synonyms JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User skills mapping
CREATE TABLE user_skills (
    user_id INT,
    skill_id INT,
    proficiency_level ENUM('beginner', 'intermediate', 'advanced', 'expert'),
    years_experience INT,
    PRIMARY KEY (user_id, skill_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
);

-- Job matches table
CREATE TABLE job_matches (
    match_id INT PRIMARY KEY AUTO_INCREMENT,
    resume_id INT,
    job_id INT,
    match_score DECIMAL(5,2),
    skill_match_percentage DECIMAL(5,2),
    experience_match DECIMAL(5,2),
    education_match DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    INDEX idx_match_score (match_score DESC),
    INDEX idx_resume_job (resume_id, job_id)
);

-- Job applications table
CREATE TABLE job_applications (
    application_id INT PRIMARY KEY AUTO_INCREMENT,
    job_id INT,
    user_id INT,
    resume_id INT,
    cover_letter TEXT,
    status ENUM('pending', 'reviewed', 'shortlisted', 'rejected', 'hired') DEFAULT 'pending',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (resume_id) REFERENCES resumes(resume_id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_applied_at (applied_at)
);
USE ai_resume_matcher;
DESCRIBE jobs;
ALTER TABLE jobs DROP COLUMN company;
ALTER TABLE jobs DROP COLUMN sources;
ALTER TABLE jobs DROP COLUMN external_url;
ALTER TABLE jobs DROP COLUMN is_active;

ALTER TABLE jobs ADD COLUMN company VARCHAR(255) DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN source VARCHAR(50) DEFAULT 'Manual';
ALTER TABLE jobs ADD COLUMN external_url TEXT DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN is_active TINYINT(1) DEFAULT 1;
ALTER TABLE job_matches ADD COLUMN score_breakdown JSON DEFAULT NULL;
DESCRIBE job_matches;
DROP TABLE job_matches;
DELETE FROM jobs WHERE source = 'LinkedIn';
-- Add external_url column if it doesn't exist
ALTER TABLE jobs ADD COLUMN external_url TEXT;

-- Add is_active column if it doesn't exist  
ALTER TABLE jobs ADD COLUMN is_active BOOLEAN DEFAULT TRUE;

-- Update existing jobs to set is_active = TRUE
UPDATE jobs SET is_active = TRUE WHERE is_active IS NULL;
USE ai_resume_matcher;
ALTER TABLE jobs ADD COLUMN url VARCHAR(800);
SELECT title, company, source, external_url,url, created_at FROM jobs ORDER BY created_at DESC LIMIT 100;
DELETE FROM jobs WHERE company = 'Multiple Companies' OR company = 'Multiple company';
-- Clean up existing search URL jobs
-- Check how many jobs will be deleted
SELECT COUNT(*) as jobs_to_delete FROM jobs 
WHERE external_url LIKE '%/jobs/search%' 
   OR external_url LIKE '%keywords=%'
   OR company = 'Multiple Companies';

-- Temporarily disable safe update mode
SET SQL_SAFE_UPDATES = 0;

-- Delete the search URL jobs
DELETE FROM jobs 
WHERE external_url LIKE '%/jobs/search%' 
   OR external_url LIKE '%keywords=%'
   OR company = 'Multiple Companies';

-- Re-enable safe update mode  
SET SQL_SAFE_UPDATES = 1;

-- Create index with key length specified
ALTER TABLE jobs ADD INDEX idx_external_url (external_url(255));

-- Verify results
SELECT COUNT(*) as remaining_jobs FROM jobs;
ALTER TABLE users ADD COLUMN reset_token VARCHAR(128);
SELECT * FROM jobs WHERE is_active = TRUE AND status = 'active';
SET SQL_SAFE_UPDATES = 0;
DELETE FROM jobs WHERE status != 'active' OR is_active = FALSE;
SET SQL_SAFE_UPDATES = 1;
SET SQL_SAFE_UPDATES = 0;
DELETE FROM jobs
WHERE LOWER(description) LIKE '%no longer accepting applications%'
   OR LOWER(requirements) LIKE '%no longer accepting applications%'
   OR LOWER(title) LIKE '%no longer accepting applications%'
   OR LOWER(description) = 'no longer accepting applications'
   OR LOWER(requirements) = 'no longer accepting applications'
   OR LOWER(title) = 'no longer accepting applications';
DELETE FROM jobs WHERE status = 'closed';
SET SQL_SAFE_UPDATES = 1;
SELECT job_id, title, description, requirements
FROM jobs
WHERE LOWER(description) LIKE '%no longer accepting applications%'
   OR LOWER(requirements) LIKE '%no longer accepting applications%'
   OR LOWER(title) LIKE '%no longer accepting applications%'
   OR LOWER(description) = 'no longer accepting applications'
   OR LOWER(requirements) = 'no longer accepting applications'
   OR LOWER(title) = 'no longer accepting applications';
SELECT * from jobs WHERE status = 'active' AND is_active = TRUE
AND description NOT LIKE '%No longer accepting applications%';