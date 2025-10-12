import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import time


def scrape_resume(url: str, session=None) -> dict:
    """Scrape details from an individual resume page."""
    if session is None:
        session = requests.Session()

    response = session.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    data = {}

    target_divs = soup.find_all("div", class_=["media-body", "single-post-body"])

    print(target_divs)
    
