import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import time

# ------------------- SCRAPER FUNCTIONS -------------------

def scrape_resume_links(category_url, max_pages=200):
    """
    Purpose: scrapes resume page URLs from a given category link that
    contains multiple paged resume listings. eg: https://www.hireitpeople.com/resume-database/63-net-developers-architects-resumes

    working logic:
    1. resume_links' to store the extracted URLs.
    2. define HTTP request headers to mimic a real web browser and avoid basic blocking mechanisms.
    3. session object is created for efficiency.
    4. loop runs from page 1 up to 'max_pages'. For each iteration:
         - constructs the page URL by appending '/page/{page}' to the category URL.
         - sends a GET request to that page.
         - if the response code is not 200, it assumes there are no more pages and stops.
         - html is parsed using bs4.
         - looks for resume links using the CSS selector 'table.hit-table h4 a'.
         - extracts the 'href' attribute of each <a> tag and adds it to the list.
         - until no links are found.
         - random delay (from 0.3 to 0.7 seconds) is added to avoid server overload or detection.
    5. returns a list of all collected resume page URLs.
    """
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
    """
    purpose: scrapes, parses and formats information from an individual resume page.
    
    working logic:
    1. session object is created if not provided, then the target resume page is requested.
    2. response is parsed using bs4's lxml parser.
    3. searches for all 'div' tags with classes 'media-body' or 'single-post-body' - these
    typically contain resume content.
    4. within each relevant div:
         - looks for all underlined (<u>) tags, which we assume indicates section headings
         like 'PROFESSIONAL EXPERIENCE' or 'TECHNICAL SKILLS'. not true btw.
         - based on the section heading, different parsing logic is applied.

       a. PROFESSIONAL EXPERIENCE:
          - initializes an empty list to store multiple job experiences.
          - finds <p> tags following the section, filters those containing <strong> tags.
          - iterates through them to extract:
              * company name
              * job role
              * additional details (like duration or achievements)
              * responsibilities (bulleted list items under <ul>)
          - stores all extracted experience entries as dictionaries in a list.

       b. TECHNICAL SKILLS:
          - creates a dictionary to store key-value pairsof skills
          [another faulty assumtion, sometimes its just a list].
          - for each <p> tag following the section (until the next <u> tag):
              * extracts the text in <strong> as the subcategory (e.g., 'Programming Languages:')
              * extracts the remaining text as the associated skills.
          - adds all extracted skills into the dictionary.

       c. OTHER SECTIONS:
          - if its something else, it searches for a following <ul> list and extracts
          each <li> item as a string.
          - stores them as a list under the corresponding section name.
    """
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
