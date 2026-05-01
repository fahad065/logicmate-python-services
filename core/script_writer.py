"""
OpenAI script writer — shared across all pipelines.
Handles YouTube long-form scripts and Instagram/Reels short scripts.
"""
import json
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def generate_youtube_script(niche: str, title: str) -> dict:
    """Generate a full YouTube video script (3-5 min)."""
    prompt = f"""You are a top YouTube scriptwriter for viral dark psychology and human behavior channels.
Your videos get millions of views because they are shocking, mysterious and deeply engaging.

Write a complete video script for: "{title}"
Niche: {niche}

SCRIPT REQUIREMENTS:
- HOOK (first 10 seconds): Start with a shocking statement, dark secret or disturbing fact that makes viewer STOP scrolling
- Build tension and mystery throughout
- Use phrases like "What I'm about to tell you...", "Most people don't know this...", "The disturbing truth is..."
- 3-5 minutes when spoken at 130 words per minute (~400-650 words)
- Add retention hooks every 45-60 seconds ("But here's where it gets darker...", "Wait until you hear this part...")
- End with a cliffhanger or shocking revelation
- Strong CTA: "Subscribe before they remove this video" or "Comment if this disturbed you"
- Conversational, bold, direct — like you're revealing forbidden knowledge

TITLE REQUIREMENTS:
- Use power words: Secret, Dark, Disturbing, Hidden, Exposed, Shocking, Warning
- Under 70 characters
- Make viewer feel they MUST watch (e.g. "The Dark Secret Behind..." / "Why They Don't Want You To Know...")

DESCRIPTION REQUIREMENTS:
- Start with a hook sentence
- 200-250 words
- Include 5-8 relevant hashtags at the end like #DarkPsychology #HumanBehavior #Psychology #MindControl
- Include timestamps placeholder
- End with subscribe CTA

TAGS: 15-20 highly searchable tags related to dark psychology, human behavior, manipulation, mind control

Return ONLY valid JSON:
{{
  "title": "Shocking SEO title with power words under 70 chars",
  "description": "Engaging description 200-250 words with hashtags at end",
  "tags": ["dark psychology", "human behavior", "manipulation tactics", "mind control", "psychology facts", "social engineering", "persuasion", "influence", "cognitive bias", "behavioral psychology", "tag11", "tag12", "tag13", "tag14", "tag15"],
  "script": "Full gripping script here...",
  "thumbnail_text": "SHOCKING 3-4 word hook for thumbnail"
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def generate_reels_script(niche: str, topic: str) -> dict:
    """Generate Instagram Reels / TikTok short script (30-60 sec)."""
    prompt = f"""You are an expert short-form video scriptwriter for viral Instagram Reels and TikTok.
Niche: {niche}
Topic: {topic}

Write a VIRAL Reels script:
- HOOK (0-3 sec): Most shocking/disturbing opening line that stops scrolling instantly
- VALUE (3-45 sec): Dark, fascinating revelations — one shocking fact every 5 seconds
- CTA (last 5 sec): "Follow for forbidden psychology" / "Save this before it's deleted"

Requirements:
- 80-120 words total
- Dark, mysterious, forbidden knowledge tone
- Short punchy sentences for fast delivery
- Written for voiceover only

Return ONLY valid JSON:
{{
  "topic": "Refined viral topic title",
  "hook": "The most shocking opening line",
  "script": "Complete voiceover script...",
  "caption": "Dark engaging Instagram caption with emojis (150 chars max)",
  "hashtags": ["#DarkPsychology", "#HumanBehavior", "#MindControl", "#Psychology", "#ForbiddenKnowledge"],
  "cover_text": "SHOCKING 3-4 word hook for cover"
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def generate_topic_ideas(niche: str, count: int = 5, format_type: str = "youtube") -> list[str]:
    """Generate trending topic ideas for a niche."""
    if format_type == "reels":
        instruction = "viral short-form Reels/TikTok videos (30-60 seconds)"
    else:
        instruction = "YouTube videos (3-5 minutes) that get millions of views"

    prompt = f"""Generate {count} highly viral {instruction} topic ideas for: {niche}

Requirements:
- Each topic must be SHOCKING, DARK or reveal a FORBIDDEN SECRET
- Must make people feel they NEED to watch immediately
- Use formats like: "The Dark Truth About...", "Why [Authority] Hides This...", "The Psychological Trick That..."
- High search potential AND viral share potential
- Never been done before angle

Return ONLY valid JSON:
{{"topics": ["topic 1", "topic 2", "topic 3"]}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.95,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("topics", [])[:count]