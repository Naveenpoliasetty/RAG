import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import time

# ------------------- SCRAPER FUNCTIONS -------------------

def scrape_resume_links(category_url, max_pages=200):
    """Scrape resume links from a given category (multiple pages)."""
    resume_links = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/116.0 Safari/537.36"
    }

    session = requests.Session()
    session.headers.update(headers)

    for page in range(1, max_pages + 1):
        url = f"{category_url}/page/{page}"
        print(f"[+] Scraping {url}")

        r = session.get(url)
        if r.status_code != 200:
            print(f"[-] Page {page} returned {r.status_code}, stopping.")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        links = [a['href'] for a in soup.select("table.hit-table h4 a")]

        if not links:  # No more resumes
            print(f"[-] No resumes found on page {page}, stopping.")
            break

        resume_links.extend(links)

        # small random delay (just to avoid hammering)
        time.sleep(random.uniform(0.3, 0.7))

    return resume_links


def scrape_resume(url: str, session=None) -> dict:
    """Scrape details from an individual resume page."""
    if session is None:
        session = requests.Session()

    response = session.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    data = {}

    target_divs = soup.find_all("div", class_=["media-body", "single-post-body"])

    for div in target_divs:
        for u_tag in div.find_all("u"):
            key = u_tag.get_text(strip=True)

            # ---------------- PROFESSIONAL EXPERIENCE ----------------
            if key == "PROFESSIONAL EXPERIENCE":
                experiences = []
                p_tags = u_tag.find_all_next("p")
                strong_p_tags = [p for p in p_tags if p.find("strong")]

                i = 0
                while i < len(strong_p_tags):
                    exp_data = {}

                    if i < len(strong_p_tags):    # company_name
                        exp_data["company_name"] = strong_p_tags[i].get_text(strip=True)
                        i += 1

                    if i < len(strong_p_tags):    # job_role
                        exp_data["job_role"] = strong_p_tags[i].get_text(strip=True)
                        i += 1

                    if i < len(strong_p_tags):    # field with strong + value
                        key3 = strong_p_tags[i].find("strong").get_text(strip=True)
                        val3 = strong_p_tags[i].get_text(strip=True).replace(key3, "").strip()
                        exp_data[key3] = val3
                        i += 1

                    if i < len(strong_p_tags):    # bulleted responsibilities
                        key4 = strong_p_tags[i].find("strong").get_text(strip=True)
                        ul_tag = strong_p_tags[i].find_next("ul")
                        if ul_tag:
                            val4 = [li.get_text(strip=True) for li in ul_tag.find_all("li")]
                        else:
                            val4 = []
                        exp_data[key4] = val4
                        i += 1

                    experiences.append(exp_data)

                data[key] = experiences

            # ---------------- TECHNICAL SKILLS ----------------
            elif key == "TECHNICAL SKILLS":
                tech_skills = {}
                for sibling in u_tag.find_all_next("p"):
                    if sibling.find("u"):
                        break
                    strong = sibling.find("strong")
                    if strong:
                        sub_key = strong.get_text(strip=True).rstrip(":")
                        sub_val = sibling.get_text(" ", strip=True).replace(strong.get_text(strip=True), "").strip()
                        if sub_val:
                            tech_skills[sub_key] = sub_val
                data[key] = tech_skills

            # ---------------- OTHER SECTIONS ----------------
            else:
                ul_tag = u_tag.find_next("ul")
                if ul_tag:
                    values = [li.get_text(strip=True) for li in ul_tag.find_all("li")]
                else:
                    values = []
                data[key] = values

    return data
