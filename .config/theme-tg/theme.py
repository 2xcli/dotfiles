#!/usr/bin/env python3
"""Build and publish the Telegram theme that follows Matugen's accent color."""

from __future__ import annotations

import argparse
import asyncio
import colorsys
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import time
import tomllib
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse


APP_DIR = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "tg-theme"
DEFAULT_LUMINOUS = Path.home() / ".config/xdg-desktop-portal-luminous/config.toml"
ACCENT_RE = re.compile(r'accent_color\s*=\s*"(#[0-9a-fA-F]{6})"')
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

FILL_KEYS = (
    "dialogsBgActive", "dialogsBgOver", "sideBarBgActive", "sideBarBgActiveOver",
    "activeButtonBg", "activeButtonBgOver", "activeButtonBgRipple", "historyFileThumbIconBg",
)
TEXT_KEYS = (
    "historyLinkInFg", "historyLinkOutFg", "windowActiveTextFg", "activeLineFg",
    "dialogsNameFgActive", "dialogsTextFgActive", "dialogsDateFgActive", "dialogsDraftFgActive",
    "activeButtonFg", "sideBarBadgeTextFg", "dialogsVerifiedIconBg",
)
ICON_KEYS = (
    "sideBarIconFgActive", "sideBarTextFgActive", "dialogsChatIconFgActive",
    "dialogsSentIconFgActive", "historySendIconFg", "historySendIconFgOver",
    "menuIconFgOver", "historyFileThumbIconFg",
)
NEUTRAL_ICON_KEYS = (
    "sideBarIconFg", "sideBarIconFgOver", "dialogsChatIconFg", "dialogsSentIconFg", "menuIconFg",
)
NEUTRAL_TEXT_KEYS = ("sideBarTextFg", "sideBarTextFgOver")


def resolve_path(value, base=APP_DIR):
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def load_config(argument):
    if argument:
        path = resolve_path(argument, Path.cwd())
    elif environment_path := os.environ.get("TG_THEME_CONFIG"):
        path = resolve_path(environment_path, Path.cwd())
    else:
        path = APP_DIR / "config.local.toml"
    if not path.exists():
        return path, {}
    with path.open("rb") as file:
        config = tomllib.load(file)
    if not isinstance(config, dict):
        raise RuntimeError(f"{path}: expected a TOML table")
    return path, config


def get_section(config, name):
    section = config.get(name, {})
    if not isinstance(section, dict):
        raise RuntimeError(f"[{name}] must be a TOML table")
    return section


def hex_to_rgb(color):
    if not HEX_RE.fullmatch(color):
        raise ValueError(f"expected #rrggbb, got {color!r}")
    return tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def mix(first, second, amount):
    return rgb_to_hex(tuple(
        round(a + (b - a) * amount)
        for a, b in zip(hex_to_rgb(first), hex_to_rgb(second))
    ))


def sanitize_accent(color):
    red, green, blue = (value / 255 for value in hex_to_rgb(color))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if hue >= .92 or hue <= .04:  # red, pink, magenta
        saturation, lightness = min(saturation, .68), min(lightness, .72)
    elif hue <= .12:  # peach, orange
        saturation, lightness = min(saturation, .74), min(lightness, .74)
    elif .70 <= hue < .92:  # violet, purple
        saturation, lightness = min(saturation, .60), min(lightness, .74)
    elif .16 <= hue <= .28:  # yellow-green, green
        saturation, lightness = min(saturation, .72), min(lightness, .64)
    elif not .50 <= hue <= .62 and saturation > .90 and lightness > .82:
        saturation, lightness = .72, .76
    return rgb_to_hex(tuple(round(value * 255) for value in colorsys.hls_to_rgb(hue, lightness, saturation)))


def fill_accent(color):
    red, green, blue = (value / 255 for value in hex_to_rgb(color))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    rgb = colorsys.hls_to_rgb(hue, min(lightness, .33), min(saturation, .32))
    return rgb_to_hex(tuple(round(value * 255) for value in rgb))


def recolor(old_color, accent):
    body = old_color[1:]
    alpha, body = (body[6:], body[:6]) if len(body) == 8 else ("", body)
    old_rgb = tuple(int(body[index:index + 2], 16) for index in (0, 2, 4))
    red, green, blue = (value / 255 for value in old_rgb)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if not (.16 <= hue <= .42 and saturation > .25 and lightness > .18):
        return old_color
    accent_hue, _, accent_saturation = colorsys.rgb_to_hls(
        *(value / 255 for value in hex_to_rgb(accent))
    )
    rgb = colorsys.hls_to_rgb(accent_hue, lightness, max(accent_saturation, .35))
    return rgb_to_hex(tuple(round(value * 255) for value in rgb)) + alpha


def read_accent(path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RuntimeError(f"Luminous config does not exist: {path}") from error
    match = ACCENT_RE.search(text)
    if not match:
        raise RuntimeError(f"accent_color was not found in {path}")
    return match.group(1)


def read_theme(path):
    if not zipfile.is_zipfile(path):
        return path.read_text(encoding="utf-8"), None
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    try:
        return files["colors.tdesktop-theme"].decode("utf-8"), files
    except KeyError as error:
        raise RuntimeError(f"{path}: colors.tdesktop-theme is missing") from error


def set_key(colors, key, value):
    replacement = f"{key}: {value};"
    colors, count = re.subn(rf"^{re.escape(key)}\s*:\s*[^;]+;", replacement, colors, flags=re.MULTILINE)
    return colors if count else f"{colors}\n{replacement}\n"


def background_bytes(color):
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError("Pillow is required for `build`; run pip install -r requirements.txt") from error
    image = Image.new("RGB", (1920, 1080), color)
    jpg, png = BytesIO(), BytesIO()
    image.save(jpg, format="JPEG", quality=100)
    image.save(png, format="PNG")
    return jpg.getvalue(), png.getvalue()


def write_theme(output, colors, files, background):
    jpg, png = background_bytes(background)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("colors.tdesktop-theme", colors.encode("utf-8"))
        for name, data in (files or {}).items():
            if name == "colors.tdesktop-theme":
                continue
            lower = name.lower()
            has_background_name = "background" in lower or "wallpaper" in lower
            if has_background_name and lower.endswith((".jpg", ".jpeg")):
                archive.writestr(name, jpg)
            elif has_background_name and lower.endswith((".png", "tiled")):
                archive.writestr(name, png)
            else:
                archive.writestr(name, data)
        if not files or "background.jpg" not in files:
            archive.writestr("background.jpg", jpg)
    return jpg


def build(config, accent_argument=None, output_argument=None):
    theme = get_section(config, "theme")
    base = resolve_path(theme.get("base", "base.tdesktop-theme"))
    output = resolve_path(output_argument, Path.cwd()) if output_argument else resolve_path(
        theme.get("output", CACHE_DIR / "matugen.tdesktop-theme")
    )
    luminous = resolve_path(theme.get("luminous_config", DEFAULT_LUMINOUS))
    background = theme.get("chat_background", "#18191d")
    hex_to_rgb(background)
    raw_accent = accent_argument or read_accent(luminous)
    hex_to_rgb(raw_accent)
    accent = sanitize_accent(raw_accent)
    colors, files = read_theme(base)
    changed = 0

    def replace(match):
        nonlocal changed
        old = match.group(0)
        new = recolor(old, accent)
        changed += new.lower() != old.lower()
        return new

    colors = re.sub(r"#[0-9a-fA-F]{6,8}", replace, colors)
    for key in FILL_KEYS:
        colors = set_key(colors, key, fill_accent(accent))
    for key in TEXT_KEYS:
        colors = set_key(colors, key, mix(accent, "#f4f7fb", .28))
    for key in ICON_KEYS:
        colors = set_key(colors, key, mix(accent, "#f5f7fa", .84))
    for key in NEUTRAL_ICON_KEYS:
        colors = set_key(colors, key, "#d4dbe3")
    for key in NEUTRAL_TEXT_KEYS:
        colors = set_key(colors, key, "#e1e6ec")
    image = write_theme(output, colors, files, background)
    fingerprint = hashlib.sha256(colors.encode("utf-8") + image).hexdigest()
    return output, raw_accent, accent, changed, fingerprint


def telegram_settings(config):
    telegram = get_section(config, "telegram")
    missing = [key for key in ("api_id", "api_hash", "slug", "title") if not telegram.get(key)]
    if missing:
        raise RuntimeError("missing in config.local.toml: " + ", ".join(missing))
    session = resolve_path(telegram.get("session", "~/.local/state/tg-theme/theme_owner"))
    legacy_session = APP_DIR / "theme_owner"
    if not session.with_suffix(".session").exists() and legacy_session.with_suffix(".session").exists():
        session = legacy_session
    session.parent.mkdir(parents=True, exist_ok=True)
    proxy = None
    if raw_proxy := str(telegram.get("proxy", "")).strip():
        parsed = urlparse(raw_proxy)
        if parsed.scheme not in {"socks4", "socks5"} or not parsed.hostname or not parsed.port:
            raise RuntimeError("telegram.proxy must look like socks5://127.0.0.1:10808")
        proxy = (parsed.scheme, parsed.hostname, parsed.port)
    return int(telegram["api_id"]), telegram["api_hash"], session, telegram["slug"], telegram["title"], proxy


async def publish(output, config):
    try:
        from telethon import TelegramClient, utils
        from telethon.errors import ThemeInvalidError
        from telethon.tl.functions.account import CreateThemeRequest, UpdateThemeRequest, UploadThemeRequest
        from telethon.tl.types import InputThemeSlug
    except ImportError as error:
        raise RuntimeError("Telethon is required for `publish`; run pip install -r requirements.txt") from error
    api_id, api_hash, session, slug, title, proxy = telegram_settings(config)
    async with TelegramClient(str(session), api_id, api_hash, proxy=proxy) as client:
        uploaded = await client.upload_file(output, file_name="matugen.tdesktop-theme")
        document = await client(UploadThemeRequest(
            file=uploaded, file_name="matugen.tdesktop-theme", mime_type="application/x-tgtheme-tdesktop",
        ))
        input_document = utils.get_input_document(document)
        try:
            await client(UpdateThemeRequest(
                format="tdesktop", theme=InputThemeSlug(slug), title=title, document=input_document,
            ))
            return "updated"
        except ThemeInvalidError:
            await client(CreateThemeRequest(slug=slug, title=title, document=input_document))
            return "created"


async def login(config):
    try:
        import qrcode
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError
    except ImportError as error:
        raise RuntimeError("qrcode and Telethon are required for `login`") from error
    api_id, api_hash, session, _, _, proxy = telegram_settings(config)
    client = TelegramClient(str(session), api_id, api_hash, proxy=proxy)
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print("already logged in:", me.username or me.first_name)
            return
        qr_login = await client.qr_login()
        qr = qrcode.QRCode(border=1)
        qr.add_data(qr_login.url)
        qr.make()
        qr.print_ascii(invert=True)
        print("\nTelegram → Settings → Devices → Link Desktop Device\n")
        try:
            user = await qr_login.wait(timeout=120)
        except SessionPasswordNeededError:
            user = await client.sign_in(password=input("2FA password: "))
        print("logged in:", user.username or user.first_name)
    finally:
        await client.disconnect()


def sync(config):
    output, raw_accent, accent, changed, fingerprint = build(config)
    state = CACHE_DIR / "last-published"
    slug = get_section(config, "telegram").get("slug", "")
    state_value = f"{slug}\t{fingerprint}\n"
    if state.exists() and state.read_text(encoding="utf-8") == state_value:
        print(f"unchanged: {accent}")
        return
    action = asyncio.run(publish(output, config))
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(state_value, encoding="utf-8")
    print(f"{action}: {raw_accent} → {accent}; recolored {changed} values")


def request_file():
    return CACHE_DIR / "requested"


def request_update(config_path):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    request_file().write_text(f"{time.time_ns()}\n", encoding="utf-8")
    with (CACHE_DIR / "worker.log").open("ab") as log:
        subprocess.Popen(
            [sys.executable, str(APP_DIR / "theme.py"), "--config", str(config_path), "worker"],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )


def request_marker():
    try:
        return request_file().read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def run_worker(config):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with (CACHE_DIR / "worker.lock").open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        delay = float(get_section(config, "theme").get("debounce_seconds", 1.5))
        if delay < 0:
            raise RuntimeError("theme.debounce_seconds must not be negative")
        while True:
            marker = request_marker()
            while True:
                time.sleep(delay)
                newer = request_marker()
                if newer == marker:
                    break
                marker = newer
            try:
                sync(config)
            except Exception as error:
                print(f"sync failed: {error}", file=sys.stderr)
            if request_marker() == marker:
                return


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", help="local TOML config; default: config.local.toml beside theme.py")
    commands = result.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="build the .tdesktop-theme archive")
    build_parser.add_argument("--accent", help="use #rrggbb instead of reading Luminous")
    build_parser.add_argument("--output", help="where to write the archive")
    commands.add_parser("publish", help="upload the current archive")
    commands.add_parser("sync", help="build and publish unless unchanged")
    commands.add_parser("login", help="authorize Telegram through a QR code")
    commands.add_parser("request", help="request a debounced background sync")
    commands.add_parser("worker", help=argparse.SUPPRESS)
    return result


def main():
    args = parser().parse_args()
    path, config = load_config(args.config)
    if args.command == "build":
        output, raw, accent, changed, _ = build(config, args.accent, args.output)
        print(f"built {output}: {raw} → {accent}; recolored {changed} values")
    elif args.command == "publish":
        output = resolve_path(get_section(config, "theme").get("output", CACHE_DIR / "matugen.tdesktop-theme"))
        if not output.exists():
            raise RuntimeError(f"theme archive does not exist: {output}; run `theme.py build` first")
        print(asyncio.run(publish(output, config)))
    elif args.command == "sync":
        sync(config)
    elif args.command == "login":
        asyncio.run(login(config))
    elif args.command == "request":
        request_update(path)
    else:
        run_worker(config)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
