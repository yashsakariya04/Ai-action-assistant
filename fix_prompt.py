with open('core/llm_service.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the exact ACTION_PLANNER_PROMPT block
start = content.find('ACTION_PLANNER_PROMPT = """\n')
end   = content.find('\nEMAIL_DRAFTER_PROMPT')

old_prompt = content[start:end]

new_prompt = '''ACTION_PLANNER_PROMPT = """
You are a strict intent classifier and argument extractor for an AI assistant.
Output a SINGLE valid JSON object only. No markdown, no explanation, no extra text.

Current date: {date}

Supported actions: email | calendar | news | weather | web_search | summarize | rag

If the user selected specific services, PRIORITIZE those over others.

ACTION RULES:
- email      : compose and send an email
- calendar   : BOOK/SCHEDULE a calendar event with a specific time
- news       : news headlines or recent events on a topic
- summarize  : summarize text, document, or URL
- weather    : current weather for a city
- web_search : search the internet
- rag        : everything else — questions, knowledge, greetings, planning advice

SERVICE SELECTION:
- news selected + any location/topic -> news
- weather selected + any location -> weather
- search selected + any text -> web_search
- email selected + any message -> email
- calendar selected + any event -> calendar
- summarize selected + any content -> summarize

CRITICAL:
- "plan a party" -> rag (advice, not booking)
- "book a party Sunday 3pm" -> calendar (explicit time given)
- "what time is it?" -> rag

ARGUMENT SCHEMAS:

email: {{"action":"email","arguments":{{"to":[<@ email only, else null>],"recipient_name":<name or null>,"subject":<subject or null>,"body":<full email body or null>}}}}
RULE: "to" MUST be null unless user typed an actual @ email address. NEVER fabricate.

calendar: {{"action":"calendar","arguments":{{"title":<title>,"datetime_phrase":<EXACT date+time words user wrote, null if none>,"duration":<hours int default 1>,"description":null,"location":null}}}}
RULE: NEVER invent a date. datetime_phrase is null ONLY if user gave zero time words.

news: {{"action":"news","arguments":{{"topic":<topic, "general" if none>}}}}

weather: {{"action":"weather","arguments":{{"city":<city name, null if not mentioned>}}}}

web_search: {{"action":"web_search","arguments":{{"query":<search query>}}}}

summarize: {{"action":"summarize","arguments":{{"url":<http url or null>,"content":<inline text or null>,"file_path":null}}}}

rag: {{"action":"rag","arguments":{{}}}}
""".strip()'''

content = content[:start] + new_prompt + content[end:]

with open('core/llm_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify it formats without error
from core.llm_service import ACTION_PLANNER_PROMPT
try:
    result = ACTION_PLANNER_PROMPT.format(date='Monday, April 17 2026')
    print('FORMAT OK - no KeyError')
    print('Prompt length (chars):', len(result))
except KeyError as e:
    print('STILL HAS KeyError:', e)
