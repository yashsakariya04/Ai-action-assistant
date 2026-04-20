"""
services/voice_service.py — Voice input (STT) service.

STT: Groq Whisper API (whisper-large-v3-turbo)
     - Ultra-fast, accurate, handles accents + background noise
     - Uses GROQ_API_KEY_PRIMARY from config

TTS: Browser Web Speech Synthesis API (client-side only)
     - No backend needed, no API key, unlimited and free
     - Upgrade path: Microsoft Azure TTS (500k chars/month free)
       or Google Cloud TTS (1M chars/month, requires billing)
"""

import logging
import os

import requests
import config

log = logging.getLogger(__name__)


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> dict:
    """
    Transcribe audio using Groq Whisper API.

    Args:
        audio_bytes: raw audio bytes from browser MediaRecorder (webm/mp4/wav/ogg)
        filename:    original filename — used for MIME type detection

    Returns:
        { "status": "success", "text": "transcribed text" }
        { "status": "error",   "message": "..." }
    """
    if not config.GROQ_API_KEY_PRIMARY:
        return {"status": "error", "message": "GROQ_API_KEY_PRIMARY not configured."}
    if not audio_bytes:
        return {"status": "error", "message": "No audio data received."}

    ext = os.path.splitext(filename)[1].lower() or ".webm"
    mime_map = {
        ".webm": "audio/webm", ".mp4": "audio/mp4",
        ".wav":  "audio/wav",  ".ogg": "audio/ogg",
        ".m4a":  "audio/mp4",  ".flac": "audio/flac",
    }
    mime_type = mime_map.get(ext, "audio/webm")

    try:
        response = requests.post(
            config.GROQ_AUDIO_URL,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY_PRIMARY}"},
            files={"file": (filename, audio_bytes, mime_type)},
            data={
                "model":           config.WHISPER_MODEL,
                "response_format": "json",
                "language":        config.WHISPER_LANGUAGE,
                "temperature":     "0",
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json().get("text", "").strip()
        if not text:
            return {"status": "error", "message": "No speech detected. Please try again."}
        log.info("Whisper transcribed %d chars from %d bytes", len(text), len(audio_bytes))
        return {"status": "success", "text": text}

    except requests.Timeout:
        return {"status": "error", "message": "Transcription timed out. Please try again."}
    except requests.HTTPError as exc:
        err = exc.response.text[:200] if exc.response else str(exc)
        log.error("Groq Whisper error: %s", err)
        return {"status": "error", "message": f"Transcription failed: {err}"}
    except Exception as exc:
        log.exception("Unexpected STT error")
        return {"status": "error", "message": f"Transcription error: {exc}"}
