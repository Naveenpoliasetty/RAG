from .prompts import PARSE_RESUME_SYSTEM_PROMPT, PARSE_RESUME_USER_PROMPT, SUMMARY_SYSTEM_PROMPT, SUMMARY_USER_PROMPT, SKILLS_SYSTEM_PROMPT, SKILLS_USER_PROMPT, EXPERIENCE_SYSTEM_PROMPT, EXPERIENCE_USER_PROMPT
import yaml
from src.utils.llm_client import load_llm_config, get_llm_model

llm_config = load_llm_config()
default_model = get_llm_model()

class LLMTask:
    def __init__(self, client, model, max_tokens):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    def run(self, messages, response_model):
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_model=response_model,
            max_tokens=self.max_tokens,
        )


class ResumeParserTask(LLMTask):
    def __init__(self, client):
        super().__init__(
            client=client,
            model=get_llm_model(),
        )

    def build_messages(self, resume_text):
        return [
            {"role": "system", "content": PARSE_RESUME_SYSTEM_PROMPT},
            {"role": "user", "content": PARSE_RESUME_USER_PROMPT.format(resume_text=resume_text)}
        ]


class Summary_experience_rewriteTask(LLMTask):
    def __init__(self, client):
        super().__init__(
            client=client,
            model=get_llm_model(),
            max_tokens=180  # for summary it is less
        )

    def build_messages(self, summary, jd):
        return [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": SUMMARY_USER_PROMPT.format(summary=summary, jd=jd)}
        ]

class TechnicalSkillsTask(LLMTask):
    def __init__(self, client):
        super().__init__(
            client=client,
            model=get_llm_model(),
            max_tokens=200  # for skills it is less
        )

    def build_messages(self, skills, jd):
        return [
            {"role": "system", "content": SKILLS_SYSTEM_PROMPT},
            {"role": "user", "content": SKILLS_USER_PROMPT.format(skills=skills, jd=jd)}
        ]

class ExperienceTask(LLMTask):
    def __init__(self, client):
        super().__init__(
            client=client,
            model=get_llm_model(),
            max_tokens=450  # for experience it is more
        )

    def build_messages(self, experience, jd):
        return [
            {"role": "system", "content": EXPERIENCE_SYSTEM_PROMPT},
            {"role": "user", "content": EXPERIENCE_USER_PROMPT.format(experience=experience, jd=jd)}
        ]