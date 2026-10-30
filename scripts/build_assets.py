"""Refresh bundled assets without Node.js or npm.

Run with Python 3.15: python scripts/build_assets.py
The normal application uses the checked-in assets and never downloads at runtime.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "src/resolvent/static/vendor"
MATHLIVE_VERSION = "0.111.1"
TAILWIND_VERSION = "4.1.18"


def download(url: str, target: Path):
    print(f"Downloading {target.name}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Resolvent-assets/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)


def mathlive():
    base = f"https://cdn.jsdelivr.net/npm/mathlive@{MATHLIVE_VERSION}"
    api = f"https://data.jsdelivr.com/v1/package/npm/mathlive@{MATHLIVE_VERSION}/flat"
    with urllib.request.urlopen(api, timeout=60) as response:
        files = json.load(response)["files"]
    for item in files:
        name = item["name"].lstrip("/")
        if name not in {"mathlive.min.js", "LICENSE.txt"} and not name.startswith(("fonts/", "sounds/")):
            continue
        dest = VENDOR / ("MATHLIVE-LICENSE.txt" if name == "LICENSE.txt" else name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        download(f"{base}/{name}", dest)


def tailwind():
    system = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system())
    machine = {"x86_64": "x64", "AMD64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    if not system or not machine:
        raise SystemExit("No standalone Tailwind binary available for this platform.")
    filename = f"tailwindcss-{system}-{machine}" + (".exe" if system == "windows" else "")
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "resolvent"
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / f"{TAILWIND_VERSION}-{filename}"
    if not binary.exists():
        partial = binary.with_suffix(".download")
        download(
            f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{TAILWIND_VERSION}/{filename}",
            partial,
        )
        partial.chmod(0o755)
        partial.replace(binary)
    subprocess.run(
        [str(binary), "-i", "frontend/app.css", "-o", "src/resolvent/static/app.css", "--minify"],
        cwd=ROOT,
        check=True,
        env={**os.environ, "NO_COLOR": "1"},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--css-only", action="store_true", help="Only rebuild CSS; retain vendored MathLive")
    args = parser.parse_args()
    VENDOR.mkdir(parents=True, exist_ok=True)
    if not args.css_only:
        mathlive()
        download(
            "https://raw.githubusercontent.com/KaTeX/KaTeX/v0.16.25/LICENSE", VENDOR / "KATEX-LICENSE.txt"
        )
    tailwind()
    files = {
        str(p.relative_to(VENDOR)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(VENDOR.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    (VENDOR / "manifest.json").write_text(
        json.dumps({"mathlive": MATHLIVE_VERSION, "files": files}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
