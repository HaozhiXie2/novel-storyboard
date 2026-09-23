"""Chinese narration with a neural voice. The line is sent to Microsoft's speech service; the novel file stays local."""
import asyncio
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

VOICE = "zh-CN-XiaoxiaoNeural"


async def synth(text, mp3):
    await edge_tts.Communicate(text, VOICE, rate="-8%").save(str(mp3))


def main():
    text = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    wav = Path(sys.argv[2])
    if not text:
        raise SystemExit("旁白是空的")
    mp3 = wav.with_suffix(".mp3")
    asyncio.run(synth(text, mp3))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(wav)],
        capture_output=True,
    )
    if result.returncode:
        raise SystemExit(result.stderr.decode("utf-8", "replace")[-800:])


if __name__ == "__main__":
    main()
