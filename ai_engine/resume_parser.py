# ai_engine/resume_parser.py

import spacy
import PyPDF2
import docx
import re
from typing import Dict, List, Optional
import json
import os

class ResumeParser:
    def __init__(self):
    # Load spaCy model with better error handling
        try:
            self.nlp = spacy.load("en_core_web_sm")
            print("spaCy model loaded successfully")
        except OSError as e:
            print(f"spaCy model loading failed: {e}")
            print("Please install spaCy English model: python -m spacy download en_core_web_sm")
            self.nlp = None
        except Exception as e:
            print(f"Unexpected error loading spaCy: {e}")
            self.nlp = None


        # Define skill patterns
        self.skill_patterns = {
            'programming': ['python', 'java', 'javascript', 'c++', 'php', 'ruby', 'go', 'rust', 'scala'],
            'web_technologies': ['html', 'css', 'react', 'angular', 'vue', 'node.js', 'django', 'flask'],
            'databases': ['mysql', 'postgresql', 'mongodb', 'sqlite', 'oracle', 'redis'],
            'tools': ['git', 'docker', 'kubernetes', 'jenkins', 'aws', 'azure', 'gcp'],
            'data_science': ['pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch', 'matplotlib']
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""

    def extract_text_from_docx(self, docx_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(docx_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return ""

    def extract_personal_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract personal information from resume text"""
        info = {
            'name': None,
            'email': None,
            'phone': None,
            'linkedin': None
        }
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            info['email'] = email_match.group()
        
        # Extract phone number
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            info['phone'] = phone_match.group()
        
        # Extract LinkedIn
        linkedin_pattern = r'linkedin\.com/in/[\w\-]+'
        linkedin_match = re.search(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_match:
            info['linkedin'] = linkedin_match.group()
        
        # Extract name (first line that looks like a name)
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line.split()) >= 2 and len(line) < 50:
                # Simple heuristic: if it's 2-4 words and doesn't contain common resume words
                words = line.split()
                if 2 <= len(words) <= 4 and not any(word.lower() in ['resume', 'cv', 'curriculum', 'vitae', 'email', 'phone'] for word in words):
                    info['name'] = line
                    break
        
        return info

    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text"""
        text_lower = text.lower()
        found_skills = []
        
        # Check all skill categories
        for category, skills in self.skill_patterns.items():
            for skill in skills:
                if skill.lower() in text_lower:
                    found_skills.append(skill)
        
        return list(set(found_skills))  # Remove duplicates

    def extract_experience(self, text: str) -> List[str]:
        """Extract work experience from resume text"""
        experience_keywords = [
            'experience', 'work experience', 'employment', 'work history',
            'professional experience', 'career', 'positions'
        ]
        
        experience_sections = []
        lines = text.split('\n')
        
        # Find experience section
        experience_start = -1
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(keyword in line_lower for keyword in experience_keywords):
                experience_start = i
                break
        
        if experience_start >= 0:
            # Extract next 10 lines after experience header
            for i in range(experience_start + 1, min(experience_start + 11, len(lines))):
                line = lines[i].strip()
                if line and len(line) > 10:  # Meaningful content
                    experience_sections.append(line)
        
        return experience_sections[:5]  # Return first 5 experience items

    def extract_education(self, text: str) -> List[str]:
        """Extract education information from resume text"""
        education_keywords = [
            'education', 'academic', 'university', 'college', 'degree',
            'bachelor', 'master', 'phd', 'diploma'
        ]
        
        education_sections = []
        text_lower = text.lower()
        
        # Look for education degrees
        degree_patterns = [
            r'bachelor[\'s]* (?:of )?(?:science|arts|engineering|business)',
            r'master[\'s]* (?:of )?(?:science|arts|engineering|business)',
            r'phd|ph\.d',
            r'doctorate',
            r'associate[\'s]* degree'
        ]
        
        for pattern in degree_patterns:
            matches = re.findall(pattern, text_lower)
            education_sections.extend(matches)
        
        return education_sections

    def parse_resume(self, file_path: str) -> Dict:
        """
        Main method to parse resume and extract all information
        """
        # Determine file type and extract text
        if file_path.lower().endswith('.pdf'):
            text = self.extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            text = self.extract_text_from_docx(file_path)
        else:
            raise ValueError("Unsupported file format. Only PDF and DOCX are supported.")
        
        if not text.strip():
            return {
                'error': 'Could not extract text from the file',
                'personal_info': {},
                'skills': [],
                'experience': [],
                'education': []
            }
        
        # Extract all information
        personal_info = self.extract_personal_info(text)
        skills = self.extract_skills(text)
        experience = self.extract_experience(text)
        education = self.extract_education(text)
        
        return {
            'raw_text': text,
            'personal_info': personal_info,
            'skills': skills,
            'experience': experience,
            'education': education,
            'total_skills_found': len(skills)
        }
