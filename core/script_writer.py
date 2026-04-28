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
    prompt = f"""You are an expert YouTube scriptwriter specializing in {niche}.

Write a complete video script for: "{title}"

Requirements:
- Hook in first 5 seconds (pattern interrupt)
- 3-5 minutes when read at normal pace (~450-750 words)
- Retention hooks every 60 seconds ("But wait...")
- Strong call to action at end (subscribe + comment)
- Conversational, not academic
- No filler words

Return ONLY valid JSON:
{{
  "title": "SEO optimized title under 60 chars",
  "description": "YouTube description 150 words with keywords",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "script": "Full script text here...",
  "thumbnail_text": "Short punchy text for thumbnail (max 5 words)"
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def generate_reels_script(niche: str, topic: str) -> dict:
    """Generate Instagram Reels / TikTok short script (30-60 sec)."""
    prompt = f"""You are an expert short-form video scriptwriter for Instagram Reels and TikTok.
Niche: {niche}
Topic: {topic}

Write a viral Reels script following this structure:
- HOOK (0-3 sec): Pattern interrupt opening line that stops scrolling
- VALUE (3-45 sec): Core content — fast paced, one point per 5 seconds
- CTA (last 5 sec): Follow for more / Save this / Comment below

Requirements:
- 80-120 words total (reads in 30-45 seconds)
- Punchy, energetic, short sentences
- Written for voiceover (no visual descriptions)
- Hashtag suggestions (15-20 relevant hashtags)

Return ONLY valid JSON:
{{
  "topic": "Refined topic title",
  "hook": "The opening hook line only",
  "script": "Complete voiceover script...",
  "caption": "Instagram caption with emojis (150 chars max)",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "cover_text": "Text overlay for cover frame (max 5 words)"
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
        instruction = "short-form viral Reels/TikTok videos (30-60 seconds)"
    else:
        instruction = "YouTube long-form videos (3-5 minutes)"

    prompt = f"""Generate {count} highly engaging {instruction} topic ideas for the niche: {niche}

Requirements:
- Each topic should be curiosity-inducing
- High search/viral potential
- Avoid overused topics
- Specific not generic

Return ONLY valid JSON:
{{"topics": ["topic 1", "topic 2", "topic 3"]}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("topics", [])[:count]