import re
from datetime import datetime
from typing import List, Dict, Optional

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string from a resume duration.
    Handles 'Present', 'Current', and various date formats.
    """
    if not date_str:
        return None
    
    date_str = date_str.strip().lower()
    
    # Handle 'Present' or 'Current'
    if 'present' in date_str or 'current' in date_str or 'now' in date_str:
        return datetime(2026, 1, 30) # Current date as requested
    
    # Month names mapping
    months = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    # Try Mon YYYY or Month YYYY
    match = re.search(r'([a-z]+)\s*(\d{4})', date_str)
    if match:
        m_str, y_str = match.groups()
        if m_str in months:
            return datetime(int(y_str), months[m_str], 1)
            
    # Try MM/YYYY or MM/YY
    match = re.search(r'(\d{1,2})/(\d{2,4})', date_str)
    if match:
        m, y = match.groups()
        if len(y) == 2:
            year = 2000 + int(y) if int(y) < 50 else 1900 + int(y)
        else:
            year = int(y)
        return datetime(year, int(m), 1)

    # Try YYYY
    match = re.search(r'(\d{4})', date_str)
    if match:
        return datetime(int(match.group(1)), 1, 1)
        
    return None

def calculate_duration_years(duration_str: str) -> float:
    """
    Calculate duration in years from a string like 'Jan 2020 - Dec 2022'
    """
    if not duration_str:
        return 0.0
    
    # Split by common separators
    parts = re.split(r'[-–—]| to | until ', duration_str)
    
    if len(parts) == 1:
        # Check if it's just a single year like '2022' (assume 1 year)
        if re.match(r'^\d{4}$', parts[0].strip()):
            return 1.0
        # Check if it explicitly says duration like '2 years'
        match = re.search(r'(\d+)\s*years?', duration_str.lower())
        if match:
            return float(match.group(1))
        return 0.0
    
    start_date = parse_date(parts[0])
    end_date = parse_date(parts[1])
    
    if start_date and end_date:
        # Ensure end is after start (sometimes people swap or have weird data)
        if end_date < start_date:
            start_date, end_date = end_date, start_date
            
        diff_days = (end_date - start_date).days
        return max(0.0, diff_days / 365.25)
    
    # Fallback: if we only have one date, we can't really know the duration
    return 0.0

def calculate_total_experience(experiences: List[Dict]) -> str:
    """
    Calculate cumulative total experience from a list of experience objects.
    Returns a string like '11+ years' or '9 months'.
    """
    total_years = 0.0
    for exp in experiences:
        duration_str = exp.get("duration", "")
        if duration_str:
            total_years += calculate_duration_years(duration_str)
    
    if total_years == 0:
        return "0 years"
    
    if total_years < 1:
        months = round(total_years * 12)
        if months == 0: months = 1
        return f"{months} month{'s' if months > 1 else ''}"
    
    # Usually people round down or use + for experience
    years = round(total_years)
    if years == 0: years = 1
    return f"{years}+ years"
