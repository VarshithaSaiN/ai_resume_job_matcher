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
