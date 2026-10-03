#!/usr/bin/env python3
"""Gemini 3.8 Flash High-Speed Audio Transcriber for Hermes."""

import argparse
import os
from pathlib import Path
import sys

from google import genai
from google.genai import types

def transcribe(input_path: Path, output_dir: Path) -> str:
    env_file = Path.home() / ".hermes" / ".env"
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break

    client = genai.Client(api_key=api_key)
    audio_bytes = input_path.read_bytes()
    suffix = input_path.suffix.lower().lstrip(".")
    mime = "audio/ogg" if suffix in ("ogg", "opus") else ("audio/mp3" if suffix == "mp3" else "audio/wav")

    resp = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
            "Transcribe this voice message verbatim into plain text. Return only the transcription."
        ]
    )
    transcript = resp.text.strip() if resp.text else ""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / (input_path.stem + ".txt")
    out_file.write_text(transcript, encoding="utf-8")
    return transcript

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("--output-dir", "--output_dir", required=True)
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--language", default="auto")
    args = parser.parse_args()

    transcribe(Path(args.input_path), Path(args.output_dir))
