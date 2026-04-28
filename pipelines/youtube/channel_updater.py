import os
from dotenv import load_dotenv

load_dotenv()


def generate_channel_description() -> str:
    from main import openai_chat

    prompt = """Write a YouTube channel description for a channel called "Knowledge Truth".
Niche: dark psychology and human behavior.
Target audience: English-speaking viewers in US, UK, Australia aged 18-35.

Rules:
- 200-250 words
- Start with a powerful hook about understanding human behavior
- Include keywords: dark psychology, human behavior, manipulation, emotional intelligence,
  psychology facts, narcissism, toxic relationships, mind control, body language
- American English spelling throughout
- End with a call to subscribe
- Do not mention AI or automation

Write only the description, no extra commentary."""

    return openai_chat(prompt, model="gpt-4o-mini", max_tokens=400)


def generate_channel_keywords() -> str:
    keywords = [
        "dark psychology", "human behavior", "psychology facts",
        "manipulation tactics", "emotional intelligence", "narcissism",
        "toxic relationships", "body language secrets", "mind control",
        "psychological tricks", "self improvement", "behavior psychology",
        "dark psychology tactics", "psychology explained", "human nature",
        "psychological analysis", "mental health awareness", "mindset",
        "behavior analysis", "psychological facts"
    ]
    return ", ".join(keywords)


def update_channel_on_first_run(first_video_id: str = None):
    """
    Update channel description, keywords and country.
    Called once after first video is uploaded.
    """
    from youtube_uploader import update_channel_info

    print("Generating channel description...")
    description = generate_channel_description()
    keywords = generate_channel_keywords()

    print("Applying channel updates...")
    update_channel_info(
        description=description,
        keywords=keywords,
        country="US",
        trailer_video_id=first_video_id
    )

    print("Channel updated successfully")
    return {"description": description, "keywords": keywords}