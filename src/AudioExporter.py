import shutil
import subprocess
from pathlib import Path


# ============================================================
# Supported Formats
# ============================================================

SUPPORTED_AUDIO_FORMATS = (
    "mp3",
    "wav",
    "flac",
    "m4a",
    "ogg",
)


# ============================================================
# Audio Export
# ============================================================

def save_audio_file(
    tts,
    audio,
    output_file: str | Path,
    output_format: str
):
    """
    Export generated RemReader audio to the requested file type.

    WAV is written directly through TTSEngine.

    MP3, FLAC, M4A and OGG are converted from a temporary WAV
    using FFmpeg. This keeps audio generation separate from
    file-format conversion.
    """

    output_file = Path(
        output_file
    )

    output_format = (
        output_format
        .lower()
        .strip()
        .lstrip(".")
    )

    if output_format not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(
            f"Unsupported output format: {output_format}. "
            f"Supported formats: "
            f"{', '.join(SUPPORTED_AUDIO_FORMATS)}."
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # -------------------------
    # Native WAV output
    # -------------------------

    if output_format == "wav":

        tts.save_audio(
            audio,
            output_file
        )

        return output_file

    # -------------------------
    # FFmpeg formats
    # -------------------------

    ffmpeg_path = shutil.which(
        "ffmpeg"
    )

    if ffmpeg_path is None:
        raise RuntimeError(
            "FFmpeg is required to export MP3, FLAC, M4A or OGG files. "
            "Install FFmpeg and make sure it is available in PATH, "
            "or select WAV output."
        )

    temp_wav = output_file.with_suffix(
        ".remreader-temp.wav"
    )

    try:

        # First save the audio in RemReader's native WAV format.
        tts.save_audio(
            audio,
            temp_wav
        )

        command = [
            ffmpeg_path,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(temp_wav),
        ]

        # -------------------------
        # Format-specific settings
        # -------------------------

        if output_format == "mp3":

            command.extend(
                [
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                ]
            )

        elif output_format == "m4a":

            command.extend(
                [
                    "-codec:a",
                    "aac",
                    "-b:a",
                    "128k",
                ]
            )

        elif output_format == "ogg":

            command.extend(
                [
                    "-codec:a",
                    "libvorbis",
                    "-q:a",
                    "4",
                ]
            )

        # FFmpeg automatically selects FLAC when the output
        # extension is .flac, so no extra codec option is needed.

        command.append(
            str(output_file)
        )

        subprocess.run(
            command,
            check=True
        )

    finally:

        # Never leave temporary conversion WAV files behind.
        if temp_wav.exists():
            temp_wav.unlink()

    return output_file