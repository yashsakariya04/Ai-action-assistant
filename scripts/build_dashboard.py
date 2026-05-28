"""One-off: rebuild dashboard.html with new shell + patched script."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
old = (ROOT / "static" / "dashboard.html").read_text(encoding="utf-8")
m = re.search(r"<script>(.*)</script>", old, re.DOTALL)
script = m.group(1).strip() if m else ""

WELCOME = r'''
function buildWelcomeHTML() {
  return `<div class="welcome" id="welcome-screen">
    <div class="welcome-icon-lg"><i data-lucide="sparkles" style="width:32px;height:32px"></i></div>
    <h2>AI Action Assistant</h2>
    <p>Your personal AI that executes real-world tasks — email, calendar, weather, search, and document summaries.</p>
    <div class="welcome-chips">
      <button type="button" class="welcome-chip" onclick="quickSend('what is the weather in Mumbai?')"><i data-lucide="cloud" class="icon-xs"></i><span>Weather in Mumbai</span></button>
      <button type="button" class="welcome-chip" onclick="quickSend('search for latest AI research')"><i data-lucide="search" class="icon-xs"></i><span>Search the web</span></button>
      <button type="button" class="welcome-chip" onclick="quickSend('get latest technology news')"><i data-lucide="newspaper" class="icon-xs"></i><span>Tech news</span></button>
      <button type="button" class="welcome-chip" onclick="quickSend('what can you do?')"><i data-lucide="message-circle" class="icon-xs"></i><span>What can you do?</span></button>
      <button type="button" class="welcome-chip" onclick="quickSend('summarize https://en.wikipedia.org/wiki/Artificial_intelligence')"><i data-lucide="file-text" class="icon-xs"></i><span>Summarize a URL</span></button>
      <button type="button" class="welcome-chip" onclick="quickSend('schedule a team meeting tomorrow at 10am')"><i data-lucide="calendar" class="icon-xs"></i><span>Schedule meeting</span></button>
    </div>
  </div>`;
}
'''

# Insert welcome builder after selectedServices
if "function buildWelcomeHTML" not in script:
    script = script.replace(
        "let selectedServices = new Set();",
        "let selectedServices = new Set();\n" + WELCOME.strip(),
    )

# Replace welcome innerHTML blocks
welcome_old = re.compile(
    r"container\.innerHTML = `<div class=\"welcome\" id=\"welcome-screen\">.*?</div>`;",
    re.DOTALL,
)
script = welcome_old.sub("container.innerHTML = buildWelcomeHTML();", script)

# toggleService
script = re.sub(
    r"function toggleService\(service\) \{.*?^\}",
    '''function toggleService(service) {
  const item = document.querySelector(`[data-service="${service}"]`);
  const cb = item.querySelector('input[type="checkbox"]');
  if (selectedServices.has(service)) {
    selectedServices.delete(service);
    item.classList.remove('selected');
    if (cb) cb.checked = false;
  } else {
    selectedServices.add(service);
    item.classList.add('selected');
    if (cb) cb.checked = true;
  }
}''',
    script,
    count=1,
    flags=re.MULTILINE | re.DOTALL,
)

# Clear services in newChat/loadHistory
script = script.replace(
    "item.querySelector('.service-checkbox').textContent = ''",
    "const _c = item.querySelector('input[type=\"checkbox\"]'); if (_c) _c.checked = false",
)

# handleFileSelect icons
script = script.replace(
    """  const icons = { pdf:'📄', docx:'📝', xlsx:'📊', txt:'📃' };
  const ext = file.name.split('.').pop().toLowerCase();
  document.getElementById('file-strip-icon').textContent = icons[ext] || '📄';""",
    """  const ext = file.name.split('.').pop().toLowerCase();
  document.getElementById('file-strip-icon').innerHTML = '<i data-lucide="file-text" class="icon-sm"></i>';
  if (typeof lucide !== 'undefined') lucide.createIcons();""",
)

# appendMessage file icon
script = script.replace(
    '<span class="file-icon">📄</span>',
    '<span class="file-icon"><i data-lucide="file-text" class="icon-sm"></i></span>',
)

# history delete
script = script.replace(
    'title="Delete">🗑</button>',
    'title="Delete"><i data-lucide="trash-2" class="icon-sm"></i></button>',
)

# renderHistory lucide
script = script.replace(
    "  }).join('');\n}",
    "  }).join('');\n  if (typeof lucide !== 'undefined') lucide.createIcons();\n}",
    1,
)

# badges
script = script.replace(
    "const badgeLabel = `${status === 'success' ? '●' : status === 'error' ? '✕' : '○'} ${status.toUpperCase()} · ${action}`;",
    "const badgeLabel = `${status.toUpperCase()} · ${action}`;",
)

# confirm buttons
script = script.replace(
    """    extra = `<div style="margin-top:10px;display:flex;gap:8px">
      <button onclick="quickConfirm('yes')" class="quick-confirm-btn" style="background:rgba(14,165,233,0.1);border:1px solid rgba(56,189,248,0.35);color:var(--sky-600)">✓ Confirm</button>
      <button onclick="quickConfirm('no')" class="quick-confirm-btn" style="background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.25);color:#b91c1c">✕ Cancel</button>
    </div>`;""",
    """    extra = `<div class="confirm-block">
      <button type="button" onclick="quickConfirm('yes')" class="btn-confirm">Confirm</button>
      <button type="button" onclick="quickConfirm('no')" class="btn-cancel">Cancel</button>
    </div>`;""",
)

# pending hint
script = script.replace(
    "font-family:var(--mono)",
    "font-family:var(--font-mono)",
)
script = script.replace(
    """    extra = `<div style="margin-top:8px;font-size:11px;color:var(--muted2);font-family:var(--font-mono)">→ Type your reply to continue</div>`;""",
    """    extra = `<div style="margin-top:8px;font-size:12px;color:var(--color-text-muted);font-family:var(--font-mono)">Type your reply to continue</div>`;""",
)

# speak emoji
script = script.replace("btn.textContent = '\\uD83D\\uDD0A Speak';", "btn.innerHTML = speakIconHtml + ' Speak';")
script = script.replace("btn.textContent = '\\uD83D\\uDD0A Speaking';", "btn.innerHTML = speakIconHtml + ' Speaking';")
script = script.replace(
    "const copyIcon = ",
    "const speakIconHtml = `<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" width=\"12\" height=\"12\"><polygon points=\"11 5 6 9 2 9 2 15 6 15 11 19 11 5\"></polygon><path d=\"M15.54 8.46a5 5 0 0 1 0 7.07\"></path></svg>`;\nconst copyIcon = ",
)

# checkHealth
script = re.sub(
    r"async function checkHealth\(\) \{.*?\n\}",
    """async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/health`);
    const data = await res.json();
    const online = data.status === 'ok' || data.status === 'degraded';
    setStatus(online ? 'Connected' : 'Degraded', online);
  } catch {
    setStatus('Offline', false);
  }
}""",
    script,
    count=1,
    flags=re.DOTALL,
)

# setStatus colors
script = script.replace(
    "document.getElementById('status-text').textContent = text;",
    "// status shown via connection dot",
)
script = script.replace(
    "document.getElementById('status-dot').style.background = online ? 'var(--accent)' : 'var(--warn)';",
    "const dot = document.getElementById('status-dot'); if (dot) dot.style.background = online ? 'var(--color-success)' : 'var(--color-warning)';",
)

# profile email init
script = script.replace(
    "(function(){\n  const name = localStorage.getItem('ai_name')",
    "(function(){\n  const email = localStorage.getItem('ai_email') || '';\n  const emailEl = document.getElementById('profile-email');\n  if (emailEl) emailEl.textContent = email;\n  const name = localStorage.getItem('ai_name')",
)

# auth me update email
script = script.replace(
    "      localStorage.setItem('ai_avatar', u.avatar_url || '');",
    """      localStorage.setItem('ai_avatar', u.avatar_url || '');
      localStorage.setItem('ai_email', u.email || '');
      const emailEl = document.getElementById('profile-email');
      if (emailEl) emailEl.textContent = u.email || '';""",
    1,
)

# typing indicator
script = script.replace(
    "<div class=\"typing\"><span></span><span></span><span></span></div>",
    "<div class=\"typing\"><span class=\"typing-dot\"></span><span class=\"typing-dot\"></span><span class=\"typing-dot\"></span></div>",
)

# messages container id - keep messages but wrap inner
# append to messages uses getElementById('messages') - change HTML id to messages

# lucide init at end
if "lucide.createIcons()" not in script.split("loadVoiceSettings()")[-1]:
    script = script.replace(
        "loadVoiceSettings();",
        "loadVoiceSettings();\nif (typeof lucide !== 'undefined') lucide.createIcons();\nupdateSendButton();\ndocument.getElementById('chat-input').addEventListener('input', updateSendButton);",
    )

send_btn_fn = """
function updateSendButton() {
  const btn = document.getElementById('send-btn');
  const input = document.getElementById('chat-input');
  if (!btn || !input) return;
  btn.disabled = (!input.value.trim() && !selectedFile) || isLoading;
}
"""
if "function updateSendButton" not in script:
    script = send_btn_fn + script

sidebar_toggle = """
function toggleSidebar() {
  document.getElementById('sidebar-drawer').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('visible');
}
function closeSidebar() {
  document.getElementById('sidebar-drawer').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('visible');
}
"""

html_head = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Action Assistant</title>
<link rel="stylesheet" href="/static/design-system.css">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
</head>
<body class="page-enter">
'''

html_body = '''
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<div class="app-shell">
  <aside class="sidebar sidebar-drawer" id="sidebar-drawer">
    <div class="sidebar-header">
      <div class="sidebar-logo">
        <div class="sidebar-logo-mark"><i data-lucide="sparkles" class="icon-md"></i></div>
        <div>
          <div class="sidebar-logo-text">AI Action Assistant</div>
          <div class="sidebar-logo-sub">Production · Agentic AI</div>
        </div>
      </div>
      <button type="button" class="new-chat-btn" onclick="newChat(); closeSidebar();">
        <i data-lucide="plus" class="icon-sm"></i>
        New conversation
      </button>
    </div>

    <div class="sidebar-section">
      <div class="section-label">Services</div>
      <div class="service-row service-item" data-service="weather" onclick="toggleService('weather')">
        <div class="service-icon-wrap"><i data-lucide="cloud" class="icon-sm"></i></div>
        <span class="service-name">Weather</span>
        <div class="toggle"><input type="checkbox" tabindex="-1" aria-hidden="true"><span class="toggle-track"></span><span class="toggle-thumb"></span></div>
      </div>
      <div class="service-row service-item" data-service="news" onclick="toggleService('news')">
        <div class="service-icon-wrap"><i data-lucide="newspaper" class="icon-sm"></i></div>
        <span class="service-name">News</span>
        <div class="toggle"><input type="checkbox" tabindex="-1" aria-hidden="true"><span class="toggle-track"></span><span class="toggle-thumb"></span></div>
      </div>
      <div class="service-row service-item" data-service="search" onclick="toggleService('search')">
        <div class="service-icon-wrap"><i data-lucide="search" class="icon-sm"></i></div>
        <span class="service-name">Web Search</span>
        <div class="toggle"><input type="checkbox" tabindex="-1" aria-hidden="true"><span class="toggle-track"></span><span class="toggle-thumb"></span></div>
      </div>
      <div class="service-row service-item" data-service="email" onclick="toggleService('email')">
        <div class="service-icon-wrap"><i data-lucide="mail" class="icon-sm"></i></div>
        <span class="service-name">Send Email</span>
        <div class="toggle"><input type="checkbox" tabindex="-1" aria-hidden="true"><span class="toggle-track"></span><span class="toggle-thumb"></span></div>
      </div>
      <div class="service-row service-item" data-service="calendar" onclick="toggleService('calendar')">
        <div class="service-icon-wrap"><i data-lucide="calendar" class="icon-sm"></i></div>
        <span class="service-name">Calendar</span>
        <div class="toggle"><input type="checkbox" tabindex="-1" aria-hidden="true"><span class="toggle-track"></span><span class="toggle-thumb"></span></div>
      </div>
      <div class="service-row service-item" data-service="summarize" onclick="toggleService('summarize')">
        <div class="service-icon-wrap"><i data-lucide="file-text" class="icon-sm"></i></div>
        <span class="service-name">Summarize</span>
        <div class="toggle"><input type="checkbox" tabindex="-1" aria-hidden="true"><span class="toggle-track"></span><span class="toggle-thumb"></span></div>
      </div>
    </div>

    <div class="history-list" id="history-list-wrap">
      <div class="section-label" style="padding-left:4px">Recent</div>
      <div id="history-list"></div>
    </div>

    <div class="sidebar-footer">
      <div id="google-connect-bar" style="display:none">
        <button type="button" class="google-connect-btn" id="google-btn" onclick="connectGoogle()">
          <i data-lucide="link" class="icon-sm"></i>
          <span id="google-btn-label">Connect Google</span>
        </button>
      </div>
      <div class="profile-btn-wrap">
        <button type="button" class="profile-btn" id="profile-btn" onclick="toggleProfileMenu()">
          <div class="profile-avatar" id="profile-avatar"><span id="profile-initials">?</span></div>
          <div class="profile-info">
            <div class="profile-name" id="profile-name">Account</div>
            <div class="profile-email-row">
              <span class="status-dot-sm dot-pulse" id="status-dot"></span>
              <span class="profile-email" id="profile-email">—</span>
            </div>
          </div>
          <span class="profile-menu-btn" aria-hidden="true"><i data-lucide="more-horizontal" class="icon-sm"></i></span>
        </button>
        <div class="profile-dropdown" id="profile-dropdown">
          <button type="button" class="dropdown-item" onclick="window.location.href='/profile'">
            <i data-lucide="user" class="icon-sm"></i><span>Profile</span>
          </button>
          <button type="button" class="dropdown-item" onclick="connectGoogle(); toggleProfileMenu();">
            <i data-lucide="link" class="icon-sm"></i><span>Connect Google</span>
          </button>
          <button type="button" class="dropdown-item" onclick="openVoiceSettings()">
            <i data-lucide="mic" class="icon-sm"></i><span>Voice settings</span>
          </button>
          <button type="button" class="dropdown-item" onclick="window.location.href='/about'">
            <i data-lucide="info" class="icon-sm"></i><span>About</span>
          </button>
          <button type="button" class="dropdown-item danger" onclick="handleSignout()">
            <i data-lucide="log-out" class="icon-sm"></i><span>Sign out</span>
          </button>
        </div>
      </div>
    </div>
  </aside>

  <main class="chat-main">
    <header class="chat-header">
      <div class="chat-header-left">
        <button type="button" class="icon-btn mobile-only" onclick="toggleSidebar()" title="Menu" aria-label="Open menu">
          <i data-lucide="menu" class="icon-md"></i>
        </button>
        <h1 class="chat-header-title muted" id="chat-title">New conversation</h1>
      </div>
      <div class="chat-header-actions">
        <button type="button" class="icon-btn" onclick="clearChat()" title="Clear chat"><i data-lucide="rotate-ccw" class="icon-md"></i></button>
        <button type="button" class="icon-btn" onclick="window.open('/docs','_blank')" title="API docs"><i data-lucide="code-2" class="icon-md"></i></button>
      </div>
    </header>

    <div class="messages-area" id="messages">
      <div class="messages-inner" id="messages-inner">
        <div class="welcome" id="welcome-screen">
          <div class="welcome-icon-lg"><i data-lucide="sparkles" style="width:32px;height:32px"></i></div>
          <h2>AI Action Assistant</h2>
          <p>Your personal AI that executes real-world tasks — email, calendar, weather, search, and document summaries.</p>
          <div class="welcome-chips">
            <button type="button" class="welcome-chip" onclick="quickSend('what is the weather in Mumbai?')"><i data-lucide="cloud" class="icon-xs"></i><span>Weather in Mumbai</span></button>
            <button type="button" class="welcome-chip" onclick="quickSend('search for latest AI research')"><i data-lucide="search" class="icon-xs"></i><span>Search the web</span></button>
            <button type="button" class="welcome-chip" onclick="quickSend('get latest technology news')"><i data-lucide="newspaper" class="icon-xs"></i><span>Tech news</span></button>
            <button type="button" class="welcome-chip" onclick="quickSend('what can you do?')"><i data-lucide="message-circle" class="icon-xs"></i><span>What can you do?</span></button>
            <button type="button" class="welcome-chip" onclick="quickSend('summarize https://en.wikipedia.org/wiki/Artificial_intelligence')"><i data-lucide="file-text" class="icon-xs"></i><span>Summarize a URL</span></button>
            <button type="button" class="welcome-chip" onclick="quickSend('schedule a team meeting tomorrow at 10am')"><i data-lucide="calendar" class="icon-xs"></i><span>Schedule meeting</span></button>
          </div>
        </div>
      </div>
    </div>

    <div class="input-area">
      <div class="input-box">
        <div class="file-strip" id="file-strip">
          <span id="file-strip-icon"><i data-lucide="file-text" class="icon-sm"></i></span>
          <span class="file-strip-name" id="file-strip-name">filename.pdf</span>
          <button type="button" class="file-strip-remove" onclick="removeFile()" aria-label="Remove file"><i data-lucide="x" class="icon-sm"></i></button>
        </div>
        <div class="input-toolbar-row">
          <label class="icon-btn" for="file-input" title="Attach file"><i data-lucide="paperclip" class="icon-md"></i></label>
          <input type="file" id="file-input" accept=".pdf,.docx,.xlsx,.txt" onchange="handleFileSelect(event)">
          <textarea id="chat-input" rows="1" placeholder="Ask anything…" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
          <button type="button" class="icon-btn mic-btn" id="mic-btn" onclick="toggleRecording()" title="Voice input"><i data-lucide="mic" class="icon-md"></i></button>
          <button type="button" class="send-btn-inline" id="send-btn" onclick="sendMessage()" title="Send" disabled><i data-lucide="arrow-up" class="icon-md"></i></button>
        </div>
        <div class="input-actions-row">
          <div class="input-actions-left">
            <button type="button" class="service-chip" onclick="quickSend('what is the weather in ')"><i data-lucide="cloud" class="icon-xs"></i> Weather</button>
            <button type="button" class="service-chip" onclick="quickSend('get latest news about ')"><i data-lucide="newspaper" class="icon-xs"></i> News</button>
            <button type="button" class="service-chip" onclick="quickSend('search for ')"><i data-lucide="search" class="icon-xs"></i> Search</button>
            <button type="button" class="service-chip" onclick="quickSend('summarize ')"><i data-lucide="file-text" class="icon-xs"></i> Summarize</button>
          </div>
          <div class="input-actions-right">
            <button type="button" class="service-chip" onclick="toggleVoicePanel()"><i data-lucide="volume-2" class="icon-xs"></i> Voice</button>
          </div>
        </div>
      </div>
      <p class="input-hint">AI can make mistakes — always verify important info</p>
    </div>
  </main>
</div>

<div class="voice-panel" id="voice-panel">
  <div class="vp-title">
    <span style="display:flex;align-items:center;gap:8px"><i data-lucide="mic" class="icon-sm"></i> Voice settings</span>
    <button type="button" class="vp-close" onclick="toggleVoicePanel()" aria-label="Close"><i data-lucide="x" class="icon-sm"></i></button>
  </div>
  <label class="vp-label" for="voice-select">Voice</label>
  <select class="vp-select" id="voice-select"></select>
  <label class="vp-label" for="speed-slider">Speed</label>
  <div class="vp-row">
    <input type="range" class="vp-slider" id="speed-slider" min="0.5" max="2" step="0.1" value="1">
    <span class="vp-val" id="speed-val">1.0x</span>
  </div>
  <label class="vp-label" for="pitch-slider">Pitch</label>
  <div class="vp-row">
    <input type="range" class="vp-slider" id="pitch-slider" min="-10" max="10" step="1" value="0">
    <span class="vp-val" id="pitch-val">0</span>
  </div>
  <div class="vp-divider"></div>
  <div class="vp-toggle-row">
    <span>Auto-speak responses</span>
    <button type="button" class="vp-toggle" id="auto-speak-toggle" onclick="toggleAutoSpeak()" aria-label="Toggle auto-speak"></button>
  </div>
</div>

<script>
''' + sidebar_toggle + '''

'''

out = html_head + html_body + script + "\n</script>\n</body>\n</html>\n"
(ROOT / "static" / "dashboard.html").write_text(out, encoding="utf-8")
print("Wrote dashboard.html", len(out), "bytes")
