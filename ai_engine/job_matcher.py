# ai_engine/job_matcher.py

import re
from typing import Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json

class JobMatcher:
    def __init__(self):
        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)
        )

        # Weight factors for different matching criteria
        self.weights = {
            'skills': 0.4,
            'experience': 0.3,
            'education': 0.2,
            'text_similarity': 0.1
        }

    def normalize_text(self, text: str) -> str:
        """Clean and normalize text for better matching"""
        text = text.lower()
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)            # Remove special chars
        text = re.sub(r'\s+', ' ', text)                       # Multiple spaces → single
        return text.strip()

    def extract_skills_from_job(self, job_description: str, job_requirements: str = "") -> List[str]:
        """Extract skills mentioned in job description and requirements"""
        combined_text = f"{job_description} {job_requirements}".lower()

        # Common technical + soft skill keywords
        skill_keywords = [
            'python', 'java', 'javascript', 'c++', 'php', 'ruby', 'go', 'rust',
            'html', 'css', 'react', 'angular', 'vue', 'node.js', 'django', 'flask',
            'mysql', 'postgresql', 'mongodb', 'sqlite', 'oracle', 'redis',
            'git', 'docker', 'kubernetes', 'jenkins', 'aws', 'azure', 'gcp',
            'machine learning', 'data science', 'artificial intelligence', 'deep learning',
            'project management', 'agile', 'scrum', 'leadership', 'communication'
        ]

        found_skills = [skill for skill in skill_keywords if skill in combined_text]
        return found_skills

    def extract_skills_from_resume(self, resume_text: str) -> List[str]:
        """Extract skills from resume text using same approach as job description"""
        resume_text = resume_text.lower()
        # Use same skill keywords list:
        skill_keywords = [
            'python', 'java', 'javascript', 'c++', 'php', 'ruby', 'go', 'rust',
            'html', 'css', 'react', 'angular', 'vue', 'node.js', 'django', 'flask',
            'mysql', 'postgresql', 'mongodb', 'sqlite', 'oracle', 'redis',
            'git', 'docker', 'kubernetes', 'jenkins', 'aws', 'azure', 'gcp',
            'machine learning', 'data science', 'artificial intelligence', 'deep learning',
            'project management', 'agile', 'scrum', 'leadership', 'communication'
        ]
        return [skill for skill in skill_keywords if skill in resume_text]

    def match_experience(self, resume_text: str, job_description: str) -> float:
        """
        Roughly match years of experience:
        - Looks for patterns like 'X years' in both resume and job description
        """
        def extract_years(text: str) -> int:
            matches = re.findall(r'(\d+)\s+year', text.lower())
            years = [int(m) for m in matches]
            return max(years) if years else 0

        resume_years = extract_years(resume_text)
        job_years = extract_years(job_description)
        if job_years == 0:
            return 1.0  # If no requirement given, full score

        return min(resume_years / job_years, 1.0)  # Clamp to 1.0

    def match_education(self, resume_text: str, job_description: str) -> float:
        """
        Match education level (basic check for Bachelor's, Master's, PhD)
        """
        education_levels = ['phd', 'master', "bachelor", "associate", "diploma", "degree"]
        resume_edus = [edu for edu in education_levels if edu in resume_text.lower()]
        job_edus = [edu for edu in education_levels if edu in job_description.lower()]

        # If no explicit job education requirement, give full score
        if not job_edus:
            return 1.0

        # If any resume education matches one in job description, score = 1.0
        return 1.0 if any(edu in resume_edus for edu in job_edus) else 0.0

    def text_similarity(self, resume_text: str, job_text: str) -> float:
        """
        Calculate cosine similarity of TF-IDF vectors of resume and job text.
        Returns value between 0.0 - 1.0
        """
        texts = [resume_text, job_text]
        tfidf_matrix = self.vectorizer.fit_transform(texts)
        cos_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(cos_sim)

    def calculate_match_score(self, resume_text: str, job_description: str, job_requirements: str = "") -> Dict:
        """
        Calculate weighted match score using skills, experience, education, and text similarity.
        Returns detailed breakdown along with final score (0-100).
        """
        # Normalize text for processing
        resume_clean = self.normalize_text(resume_text)
        job_clean = self.normalize_text(f"{job_description} {job_requirements}")

        # Skills match
        resume_skills = set(self.extract_skills_from_resume(resume_clean))
        job_skills = set(self.extract_skills_from_job(job_description, job_requirements))
        skill_overlap = len(resume_skills.intersection(job_skills)) / len(job_skills) if job_skills else 0

        # Experience match
        exp_score = self.match_experience(resume_clean, job_clean)

        # Education match
        edu_score = self.match_education(resume_clean, job_clean)

        # Text similarity
        text_sim_score = self.text_similarity(resume_clean, job_clean)

        # Weighted final score
        final_score = (
            (skill_overlap * self.weights['skills']) +
            (exp_score * self.weights['experience']) +
            (edu_score * self.weights['education']) +
            (text_sim_score * self.weights['text_similarity'])
        ) * 100.0

        return {
            "final_score": round(final_score, 2),
            "skills_score": round(skill_overlap * 100, 2),
            "experience_score": round(exp_score * 100, 2),
            "education_score": round(edu_score * 100, 2),
            "text_similarity_score": round(text_sim_score * 100, 2),
            "matched_skills": list(resume_skills.intersection(job_skills)),
            "missing_skills": list(job_skills.difference(resume_skills))
        }

# Usage Example
if __name__ == "__main__":
    matcher = JobMatcher()

    resume_text = """
        Experienced Python developer with 5 years in Django, Flask, MySQL.
        Skilled in machine learning, Docker, AWS.
        Holds a Master's in Computer Science.
    """
    job_description = """
        Seeking a backend developer proficient in Python, Django, MySQL,
        with at least 3 years' experience. Knowledge of AWS and Docker is a plus.
        Bachelor's degree required.
    """
    job_requirements = """
        Skills: Python, Django, MySQL, Docker, AWS.
        Experience: Minimum 3 years.
        Education: Bachelor's degree.
    """

    result = matcher.calculate_match_score(resume_text, job_description, job_requirements)
    print(json.dumps(result, indent=2))
