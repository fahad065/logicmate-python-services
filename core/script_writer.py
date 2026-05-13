"""
OpenAI script writer — shared across all pipelines.
Handles YouTube long-form scripts and Instagram/Reels short scripts.
"""
import json
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# OpenAI pricing (GPT-4o-mini)
OPENAI_PRICE_PER_1K_INPUT  = 0.00015   # $0.15 per 1M input tokens
OPENAI_PRICE_PER_1K_OUTPUT = 0.0006    # $0.60 per 1M output tokens

def calculate_openai_cost(usage) -> float:
    """Calculate cost from OpenAI usage object."""
    if not usage:
        return 0.0
    input_cost  = (usage.prompt_tokens / 1000) * OPENAI_PRICE_PER_1K_INPUT
    output_cost = (usage.completion_tokens / 1000) * OPENAI_PRICE_PER_1K_OUTPUT
    return round(input_cost + output_cost, 6)

def generate_youtube_script(niche: str, topic: str) -> tuple[dict, float]:
    """Generate full YouTube script. Returns (script_data, cost)."""
    total_cost = 0.0
 
    # Script generation
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""You are an expert YouTube scriptwriter. Write a detailed, engaging YouTube video script about "{topic}" in the niche of {niche}.
            The script must be 1500-2000 words long to fill a 7-8 minute video. Structure it as:
            - HOOK (0-30s): Shocking opening that grabs attention immediately
            - INTRO (30s-1min): Brief overview of what viewer will learn
            - MAIN CONTENT (1min-6min): 4-5 detailed sections with fascinating revelations, examples, and stories
            - CONCLUSION (6min-7min): Key takeaways and call to action

            Writing style: Dark, mysterious, authoritative. Short punchy sentences. Build suspense throughout.

            Return ONLY valid JSON:
            {{
                "title": "engaging clickbait YouTube title with numbers or shock value",
                "description": "YouTube description (200 words) with timestamps and keywords",
                "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
                "script": "full narration script (1500-2000 words, detailed with all sections)",
                "thumbnail_text": "short punchy 3-5 word text for thumbnail"
            }}"""}],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    total_cost += calculate_openai_cost(resp.usage)
 
    import json
    data = json.loads(resp.choices[0].message.content)
    return data, total_cost


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


def generate_topic_ideas(niche: str, count: int = 3, format_type: str = "youtube") -> tuple[list, float]:
    """Generate topic ideas. Returns (topics, cost)."""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""Generate {count} viral {format_type} video topics for niche: {niche}
Return ONLY valid JSON: {{"topics": ["topic1", "topic2", ...]}}"""}],
        response_format={"type": "json_object"},
        temperature=0.9,
    )
    cost = calculate_openai_cost(resp.usage)
    import json
    data = json.loads(resp.choices[0].message.content)
    return data.get("topics", [f"The dark truth about {niche}"]), cost