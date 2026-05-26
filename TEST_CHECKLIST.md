# AI Action Assistant — Manual QA Checklist

Run each test in a **fresh session** (or `/reset`) unless noted.  
Verify the **status badge** (● SUCCESS / ○ PENDING / ○ AWAITING / ○ CANCELLED) and **action type** match expected.

---

## Test 1 — Greeting

| Step | Input | Expected |
|------|-------|----------|
| 1 | `hey` | ● SUCCESS · **GREETING** — lists 6 capabilities (email, calendar, weather, news, web search, summarize). No casual small talk. No LLM-style filler. |

---

## Test 2 — Email with partial fields in one message

| Step | Input | Expected |
|------|-------|----------|
| 1 | `send a mail to test@gmail.com about project update` | ○ PENDING · **EMAIL** — asks for **body only** (to + subject already extracted). |

---

## Test 3 — Email auto-generate body

| Step | Input | Expected |
|------|-------|----------|
| 1 | `send email to test@gmail.com` | ○ PENDING · EMAIL — asks for subject, then body |
| 2 | (provide subject if asked) | ○ PENDING · EMAIL — asks for body |
| 3 | `auto generate` | ○ AWAITING · **EMAIL** — confirmation preview with LLM-generated body. **No** ● SUCCESS until you confirm. |

---

## Test 4 — Email body from weather context

| Step | Input | Expected |
|------|-------|----------|
| 1 | `weather in Mumbai` | ● SUCCESS · **WEATHER** — real weather data |
| 2 | `send a mail to test@gmail.com about weather` | ○ PENDING · EMAIL — field collection |
| 3 | (complete to/subject if needed) | |
| 4 | `use the weather data` | ○ AWAITING · **EMAIL** — body contains last weather result, preview shown |

---

## Test 5 — Calendar with date/time in one message

| Step | Input | Expected |
|------|-------|----------|
| 1 | `schedule a meeting tomorrow at 3 pm` | ○ PENDING · **CALENDAR** — asks for **title only** (date + time extracted). |

---

## Test 6 — Calendar missing all fields

| Step | Input | Expected |
|------|-------|----------|
| 1 | `schedule something` | ○ PENDING · **CALENDAR** — asks: *"What is the title or purpose of this event?"* |

---

## Test 7 — Cancel during email collection

| Step | Input | Expected |
|------|-------|----------|
| 1 | `send email to test@gmail.com` | ○ PENDING · EMAIL |
| 2 | `exit` or `cancel` | ○ CANCELLED · **NONE** — `"Action cancelled."` — all pending state cleared |

---

## Test 8 — New intent overrides stale pending state

| Step | Input | Expected |
|------|-------|----------|
| 1 | `send email to test@gmail.com` | ○ PENDING · EMAIL |
| 2 | `schedule meeting tomorrow at 2pm` | Email state cleared silently. ○ PENDING · **CALENDAR** (or asks for title). **No** "email already sent" message. |

---

## Test 9 — Web search (deterministic)

| Step | Input | Expected |
|------|-------|----------|
| 1 | `who is virat kohli` | ● SUCCESS · **WEB_SEARCH** — every time, never RAG |
| 2 | (new session) repeat same query | Same result: WEB_SEARCH |

---

## Test 10 — Calendar confirmation and execution

| Step | Input | Expected |
|------|-------|----------|
| 1 | `schedule a reminder for next friday 3 pm` | ○ PENDING then ○ AWAITING · **CALENDAR** after fields collected |
| 2 | `yes` | ● SUCCESS · **CALENDAR** — real Google Calendar API called; event link or confirmation shown. **Not** RAG hallucination. |

---

## Regression checks

- [ ] `okay send this mail to shlok.infopulsetech@gmail.com` → ○ PENDING · EMAIL (not RAG success)
- [ ] `schedule a reminder for next friday 3 pm` → ○ PENDING/CALENDAR (not RAG success)
- [ ] `what can you do` → lists **only** integrated capabilities (no generic AI list)
- [ ] No numbered menus (`1. … 2. …`) in any response
- [ ] Email/calendar never show ● SUCCESS without preview + `yes` first

---

## Automated pre-classifier smoke test

```bash
python -c "
from backend.chat_engine import pre_classify_intent
cases = [
    ('hey', 'greeting'),
    ('send mail to x@gmail.com', 'email'),
    ('schedule meeting tomorrow 3pm', 'calendar'),
    ('weather in bhuj', 'weather'),
    ('who is virat kohli', 'web_search'),
    ('latest news on politics', 'news'),
    ('cancel', 'cancel'),
]
all_pass = True
for msg, expected in cases:
    got = pre_classify_intent(msg)
    status = 'PASS' if got == expected else 'FAIL'
    print(f'{status}  \"{msg}\" -> {got} (expected {expected})')
    if got != expected: all_pass = False
print()
print('ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED')
"
```
