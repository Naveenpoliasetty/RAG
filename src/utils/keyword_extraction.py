import re
from collections import Counter
import spacy
from wordfreq import zipf_frequency

# Load SpaCy model
nlp = spacy.load("en_core_web_sm")

# English + job boilerplate stopwords
STOPWORDS = set(nlp.Defaults.stop_words).union({
    "responsibilities", "requirements", "requirement", "qualification",
    "qualifications", "responsible", "candidate", "role", "position",
    "skills", "ability", "abilities", "experience", "team", "work",
    "years", "job", "environment", "department"
})

def is_acronym(token):
    return bool(re.fullmatch(r"[A-Z0-9\-\.]{2,}", token))

def is_common_word(word):
    """
    Uses word frequency (Zipf score). Higher = more common.
    Common English words have Zipf >= 4.0 typically.
    Technical terms tend to have low frequency.
    """
    return zipf_frequency(word.lower(), "en") >= 4.0

def extract_candidates(text):
    doc = nlp(text)
    candidates = []

    for token in doc:
        if token.pos_ in ("NOUN", "PROPN"):
            w = token.text.strip()
            if len(w) > 1 and w.lower() not in STOPWORDS:
                candidates.append(w)
        # Acronym pattern
        if is_acronym(token.text):
            candidates.append(token.text)


    for chunk in doc.noun_chunks:
        phrase = chunk.text.strip()
        # Remove chunks that are entirely stopwords
        if not all(w.lower() in STOPWORDS for w in phrase.split()):
            candidates.append(phrase)

    return candidates

def score_terms(candidates):
    # Count frequency in the JD
    freq = Counter([c for c in candidates])

    scored = {}
    for term, count in freq.items():
        # Base score = frequency
        score = count

        # Boost acronyms (high chance of being tech)
        if is_acronym(term):
            score *= 2.0

        # Penalize common everyday English words
        if is_common_word(term):
            score *= 0.4

        # Boost multi-word technical phrases
        if " " in term:
            score *= 1.3

        scored[term] = score

    return scored


def extract_keywords(text, min_score=0.9):
    candidates = extract_candidates(text)
    scored = score_terms(candidates)

    sorted_terms = sorted(scored.items(), key=lambda x: x[1], reverse=True)

    return [term.lower() for term, score in sorted_terms if score >= min_score]
