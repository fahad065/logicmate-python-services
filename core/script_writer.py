"""
OpenAI script writer — shared across all pipelines.
Handles YouTube long-form scripts and Instagram/Reels short scripts.
"""
import json
from openai import OpenAI
from core.config import OPENAI_API_KEY
from core.model_health import get_best_openai_chat_model

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

    prompt = f"""You are an expert YouTube scriptwriter and SEO specialist. Write a detailed, engaging YouTube video script about "{topic}" in the niche of {niche}.

        The script MUST be between 1500-2000 words. Count the words carefully. If your script is less than 1500 words, add more detail, examples, and stories.
        
        Structure:
        - HOOK (0-30s): Shocking opening
        - INTRO (30s-1min): Overview
        - MAIN CONTENT (1min-6min): 4-5 detailed sections with stories and examples
        - CONCLUSION (6min-7min): Takeaways and CTA
        
        Writing style: Dark, mysterious, authoritative. Short punchy sentences.
        
        For description: 300-word SEO description with timestamps and hashtags.
        
        For tags: 40-50 simple keyword tags. Rules: NO hashtags, NO special characters, NO commas within a tag, only letters numbers and spaces. Example: dark psychology, manipulation tactics, human behavior
        
        Return ONLY valid JSON:
        {{
            "title": "engaging clickbait title (max 100 chars)",
            "description": "300-word SEO description with timestamps and hashtags",
            "tags": ["dark psychology", "manipulation tactics", ...40-50 clean simple tags],
            "script": "FULL narration script — MUST BE 1500-2000 WORDS",
            "thumbnail_text": "3-5 word thumbnail text"
        }}"""

    resp = client.chat.completions.create(
        model=get_best_openai_chat_model(),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=6000,
    )
    total_cost += calculate_openai_cost(resp.usage)

    import json
    data = json.loads(resp.choices[0].message.content)

    # Verify script length — retry if too short
    script = data.get("script", "")
    word_count = len(script.split())
    print(f"  [Script] Word count: {word_count}", flush=True)

    if word_count < 800:
        print(f"  [Script] Too short ({word_count} words) — retrying...", flush=True)
        resp2 = client.chat.completions.create(
            model=get_best_openai_chat_model(),
            messages=[{"role": "user", "content": f"""You are a YouTube scriptwriter. Write a detailed script about "{topic}" for {niche} niche.

CRITICAL: The "script" field MUST be at least 1500 words. Count carefully.

Return ONLY this JSON format:
{{
    "title": "engaging YouTube title (max 100 chars)",
    "description": "300-word SEO description with timestamps and hashtags",
    "tags": ["tag1", "tag2", "tag3"],
    "script": "FULL script here — minimum 1500 words, include hook, intro, 4-5 main sections with examples and stories, conclusion with CTA",
    "thumbnail_text": "3-5 word text"
}}"""}],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=6000,
        )
        total_cost += calculate_openai_cost(resp2.usage)
        data2 = json.loads(resp2.choices[0].message.content)
        if data2.get("description") and data2.get("script"):
            retry_count = len(data2.get("script", "").split())
            print(f"  [Script] Retry word count: {retry_count}", flush=True)
            data = data2
        else:
            print(f"  [Script] Retry missing fields — keeping original", flush=True)

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
        model=get_best_openai_chat_model(),
        messages=[{"role": "user", "content": f"""Generate {count} viral {format_type} video topics for niche: {niche}
            Return ONLY valid JSON: {{"topics": ["topic1", "topic2", ...]}}"""}],
        response_format={"type": "json_object"},
        temperature=0.9,
    )
    cost = calculate_openai_cost(resp.usage)
    import json
    data = json.loads(resp.choices[0].message.content)
    return data.get("topics", [f"The dark truth about {niche}"]), cost