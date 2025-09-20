import re
from bs4 import BeautifulSoup
from threading import Thread
from flask_mail import Message
from app import app, mail

def strip_html_tags(text):
    """Remove HTML tags from text and return clean text."""
    if not text:
        return ""

    try:
        soup = BeautifulSoup(text, "html.parser")
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        clean_text = soup.get_text(separator=" ", strip=True)
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text
    except Exception:
        clean_re = re.compile('<.*?>')
        return re.sub(clean_re, '', text).strip()

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, recipients, body):
    msg = Message(subject, recipients=recipients, body=body, sender=app.config['MAIL_USERNAME'])
    Thread(target=send_async_email, args=(app, msg), daemon=True).start()
