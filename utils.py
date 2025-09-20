# utils.py
import re
from bs4 import BeautifulSoup

def strip_html_tags(text):
    """Remove HTML tags from text and return clean text"""
    if not text:
        return ""
    
    # Using BeautifulSoup for robust HTML cleaning
    try:
        soup = BeautifulSoup(text, "html.parser")
        # Remove script and style elements completely
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean up whitespace
        clean_text = soup.get_text(strip=True)
        # Replace multiple spaces with single space
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text
    except:
        # Fallback to regex if BeautifulSoup fails
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()
from threading import Thread
from flask_mail import Message
from app import app,mail

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, recipients, body):
    msg = Message(subject, recipients=recipients, body=body, sender=app.config['MAIL_USERNAME'])
    Thread(target=send_async_email, args=(app, msg), daemon=True).start()
