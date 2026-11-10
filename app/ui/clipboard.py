"""Copy text to the system clipboard (`/copy`, D-068 step 1). Standard library only; never raises."""
from __future__ import annotations

import shutil
import subprocess
import sys


def copy(text: str) -> bool:
    try:
        if sys.platform == "win32":
            # clip.exe takes UTF-16 LE: plain UTF-8 garbles non-ASCII, and "utf-16" adds a byte-order mark that
            # lands in the pasted text (checked live 2026-11-10)
            subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True, timeout=10)
            return True
        for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=10)
                return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False
