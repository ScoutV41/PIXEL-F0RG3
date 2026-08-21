#!/usr/bin/env python3
"""
PIXEL FORGE
A self-contained, portable, terminal-based image editor.
Arrow keys + Enter to navigate. Live colored ANSI preview of your images
right inside the terminal (Windows Terminal / cmd / PowerShell / any
modern Linux/Mac terminal). Only dependency: Pillow.

Run:  python app.py
"""

import os
import sys
import shutil
import copy
from pathlib import Path

try:
    from PIL import Image, ImageEnhance, ImageOps, ImageFilter
except ImportError:
    print("Pillow is required. Install it with:\n    pip install Pillow --break-system-packages")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Cross-platform single-keypress reader (arrow keys, enter, esc, backspace)
# ---------------------------------------------------------------------------

WINDOWS = os.name == "nt"

if WINDOWS:
    import msvcrt
else:
    import tty
    import termios


def _enable_windows_ansi():
    """Turn on ANSI escape processing for legacy cmd.exe / older consoles."""
    if not WINDOWS:
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def get_key():
    """Blocks until a key is pressed, returns a normalized string:
    'UP','DOWN','LEFT','RIGHT','ENTER','ESC','BACKSPACE', or a raw char."""
    if WINDOWS:
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            return {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}.get(ch2, "")
        if ch == b"\r":
            return "ENTER"
        if ch == b"\x1b":
            return "ESC"
        if ch == b"\x08":
            return "BACKSPACE"
        try:
            return ch.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    else:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                rest = sys.stdin.read(2)
                return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(rest, "ESC")
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch == "\x7f":
                return "BACKSPACE"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ---------------------------------------------------------------------------
# Color / drawing helpers
# ---------------------------------------------------------------------------

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"


def fg(r, g, b):
    return f"\x1b[38;2;{r};{g};{b}m"


def bg(r, g, b):
    return f"\x1b[48;2;{r};{g};{b}m"


CYAN = fg(80, 220, 240)
MAGENTA = fg(255, 90, 200)
YELLOW = fg(255, 210, 90)
GREEN = fg(120, 230, 140)
RED = fg(255, 90, 90)
GREY = fg(150, 150, 160)
WHITE = fg(240, 240, 245)

RAINBOW = [
    fg(255, 90, 90), fg(255, 170, 80), fg(255, 220, 90),
    fg(150, 230, 120), fg(90, 220, 210), fg(110, 170, 255), fg(200, 120, 255),
]


def clear():
    print("\x1b[2J\x1b[H", end="")


def term_size():
    size = shutil.get_terminal_size(fallback=(100, 32))
    return size.columns, size.lines


# 5-row block font for the banner (only the letters we need)
FONT = {
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "X": ["#   #", " # # ", "  #  ", " # # ", "#   #"],
    "E": ["#####", "#    ", "###  ", "#    ", "#####"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "###  ", "#    ", "#    "],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "G": [" ### ", "#    ", "# ###", "#   #", " ### "],
    " ": ["     ", "     ", "     ", "     ", "     "],
}


def banner(text):
    rows = ["", "", "", "", ""]
    for ch in text:
        glyph = FONT.get(ch.upper(), FONT[" "])
        for i in range(5):
            rows[i] += glyph[i] + "  "
    lines = []
    for i, row in enumerate(rows):
        color = RAINBOW[i % len(RAINBOW)]
        colored = "".join(color + c if c == "#" else " " for c in row)
        lines.append(colored + RESET)
    return "\n".join(lines)


def hline(width, color=CYAN, ch="─"):
    return color + ch * width + RESET


def header_lines(subtitle=""):
    """Builds the header as a list of lines (without printing) so callers
    can budget remaining terminal rows against it."""
    cols, _ = term_size()
    lines = banner("PIXEL FORGE").split("\n")
    if subtitle:
        lines.append(DIM + WHITE + f"  {subtitle}" + RESET)
    lines.append(hline(min(cols, 78)))
    lines.append("")
    return lines


def print_header(subtitle=""):
    clear()
    for line in header_lines(subtitle):
        print(line)


# ---------------------------------------------------------------------------
# Arrow-key menu (with viewport scrolling + optional extra content, e.g. an
# image preview, rendered as part of the same frame so it never gets wiped
# by the next redraw)
# ---------------------------------------------------------------------------

def menu(title, options, subtitle=None, footer="↑/↓ move   Enter select   Esc back", extra=None):
    """options: list of strings, or list of (label, disabled_bool) tuples.
    extra: optional pre-rendered multi-line string (e.g. an image preview)
    shown above the title, as part of the same frame as the menu."""
    norm = []
    for opt in options:
        if isinstance(opt, tuple):
            norm.append(opt)
        else:
            norm.append((opt, False))

    idx = 0
    scroll = 0
    while True:
        cols, term_lines = term_size()

        head = header_lines(subtitle)
        extra_lines = extra.split("\n") if extra else []
        # Fixed chrome: header + (extra + blank) + title + blank + footer blank
        # + footer text + 2 lines reserved for scroll indicators.
        fixed = len(head) + (len(extra_lines) + 1 if extra else 0) + 2 + 2 + 2
        window = max(3, term_lines - fixed)
        window = min(window, len(norm))

        # Keep the cursor inside the visible window, scrolling minimally.
        if idx < scroll:
            scroll = idx
        elif idx >= scroll + window:
            scroll = idx - window + 1
        scroll = max(0, min(scroll, max(0, len(norm) - window)))

        clear()
        for line in head:
            print(line)
        if extra:
            print(extra)
            print()
        print(BOLD + MAGENTA + f"  {title}" + RESET)
        print()

        if scroll > 0:
            print(DIM + GREY + f"  ▲ {scroll} more above" + RESET)
        else:
            print()

        visible = norm[scroll:scroll + window]
        for offset, (label, disabled) in enumerate(visible):
            i = scroll + offset
            if i == idx:
                cursor = YELLOW + "  ➤ " + RESET
                text_color = BOLD + WHITE if not disabled else DIM + GREY
                print(cursor + text_color + label + RESET)
            else:
                text_color = WHITE if not disabled else DIM + GREY
                print("    " + text_color + label + RESET)

        remaining_below = len(norm) - (scroll + window)
        if remaining_below > 0:
            print(DIM + GREY + f"  ▼ {remaining_below} more below" + RESET)
        else:
            print()

        print()
        print(DIM + GREY + "  " + footer + RESET)

        key = get_key()
        if key == "UP":
            idx = (idx - 1) % len(norm)
        elif key == "DOWN":
            idx = (idx + 1) % len(norm)
        elif key == "ENTER":
            if not norm[idx][1]:
                return idx
        elif key == "ESC":
            return -1


def text_prompt(prompt, default=""):
    """Falls back to normal line input (not raw mode) for typing text."""
    print()
    sys.stdout.write(CYAN + f"  {prompt}" + (f" [{default}]" if default else "") + ": " + RESET)
    sys.stdout.flush()
    try:
        val = input()
    except (EOFError, KeyboardInterrupt):
        return default
    return val.strip() or default


def pause(msg="Press Enter to continue..."):
    print()
    print(DIM + GREY + "  " + msg + RESET)
    while True:
        k = get_key()
        if k in ("ENTER", "ESC"):
            return


# ---------------------------------------------------------------------------
# Terminal image rendering (ANSI truecolor half-blocks)
# ---------------------------------------------------------------------------

def render_image(img, max_width=None, max_height=None):
    """Renders img as ANSI truecolor half-blocks (▀), always preserving
    aspect ratio: whichever of width/height is the tighter constraint
    determines the scale, so the image is never stretched or squashed."""
    cols, lines = term_size()
    max_width = max_width or min(cols - 4, 220)
    max_height = max_height or (lines - 12) * 2

    src = img.convert("RGB")
    w, h = src.size
    if w == 0 or h == 0:
        return ""

    # max_height is in "pixel row" units (each printed text row = 2 pixel
    # rows), so it's directly comparable to max_width (1 pixel col = 1
    # char col). Whichever axis is tighter sets the scale — this is what
    # keeps the render from being squashed to fit a short menu below it.
    scale = min(max_width / w, max_height / h)
    new_w = max(1, round(w * scale))
    new_h = max(2, round(h * scale))
    if new_h % 2 != 0:
        new_h += 1

    resample = getattr(Image, "Resampling", Image).BOX
    small = src.resize((new_w, new_h), resample=resample)
    px = small.load()
    w2, h2 = small.size

    out_lines = []
    for y in range(0, h2 - 1, 2):
        parts = []
        for x in range(w2):
            r1, g1, b1 = px[x, y]
            r2, g2, b2 = px[x, y + 1]
            parts.append(f"{fg(r1, g1, b1)}{bg(r2, g2, b2)}\u2580")
        out_lines.append("".join(parts) + RESET)
    return "\n".join(out_lines)


def render_image_fit(img, max_rows, max_cols=None):
    """Renders img so the OUTPUT is at most max_rows printed lines tall
    (and max_cols wide). Use this when you need to know in advance how
    much vertical space the preview will take, e.g. to leave room for a
    menu below it."""
    max_rows = max(2, max_rows)
    cols, _ = term_size()
    max_cols = max_cols or min(cols - 4, 220)
    return render_image(img, max_width=max_cols, max_height=max_rows * 2)


# ---------------------------------------------------------------------------
# File browsing
# ---------------------------------------------------------------------------

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}


def candidate_folders():
    home = Path.home()
    folders = [
        ("Pictures", home / "Pictures"),
        ("Downloads", home / "Downloads"),
        ("Desktop", home / "Desktop"),
        ("Documents", home / "Documents"),
        ("Current Folder", Path.cwd()),
    ]
    return [(name, p) for name, p in folders if p.exists()]


def list_images(folder: Path):
    try:
        files = sorted(
            [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS],
            key=lambda f: f.name.lower(),
        )
    except (PermissionError, FileNotFoundError):
        files = []
    return files


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def apply_warm(img):
    r, g, b = img.convert("RGB").split()
    r = r.point(lambda v: min(255, int(v * 1.15) + 8))
    b = b.point(lambda v: max(0, int(v * 0.88)))
    out = Image.merge("RGB", (r, g, b))
    return ImageEnhance.Color(out).enhance(1.15)


def apply_cool(img):
    r, g, b = img.convert("RGB").split()
    b = b.point(lambda v: min(255, int(v * 1.15) + 8))
    r = r.point(lambda v: max(0, int(v * 0.9)))
    out = Image.merge("RGB", (r, g, b))
    return ImageEnhance.Color(out).enhance(1.05)


def apply_sunny(img):
    out = ImageEnhance.Brightness(img).enhance(1.12)
    out = ImageEnhance.Contrast(out).enhance(1.1)
    out = apply_warm(out)
    return ImageEnhance.Color(out).enhance(1.1)


def apply_noir(img):
    out = ImageOps.grayscale(img).convert("RGB")
    return ImageEnhance.Contrast(out).enhance(1.35)


def apply_vintage(img):
    grey = ImageOps.grayscale(img)
    sepia = ImageOps.colorize(grey, black=(40, 26, 13), white=(255, 240, 200))
    out = ImageEnhance.Contrast(sepia).enhance(0.9)
    return ImageEnhance.Brightness(out).enhance(1.02)


def apply_vivid(img):
    out = ImageEnhance.Color(img).enhance(1.5)
    out = ImageEnhance.Contrast(out).enhance(1.2)
    return ImageEnhance.Sharpness(out).enhance(1.3)


def apply_grayscale(img):
    return ImageOps.grayscale(img).convert("RGB")


FILTERS = {
    "Warm": apply_warm,
    "Cool": apply_cool,
    "Sunny": apply_sunny,
    "Noir (B&W high contrast)": apply_noir,
    "Vintage / Sepia": apply_vintage,
    "Vivid": apply_vivid,
    "Grayscale": apply_grayscale,
}


# ---------------------------------------------------------------------------
# Editing session (undo stack lives here)
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, path: Path):
        self.path = path
        self.original = Image.open(path).convert("RGB")
        self.working = self.original.copy()
        self.history = []
        self.dirty = False

    def push_history(self):
        self.history.append(self.working.copy())
        if len(self.history) > 20:
            self.history.pop(0)

    def apply(self, new_img):
        self.push_history()
        self.working = new_img
        self.dirty = True

    def undo(self):
        if self.history:
            self.working = self.history.pop()
            self.dirty = True
            return True
        return False

    def reset(self):
        self.push_history()
        self.working = self.original.copy()
        self.dirty = True

    def preview_copy(self):
        cols, lines = term_size()
        w = min(cols - 4, 220)
        h = (lines - 14) * 2
        img = self.working.copy()
        img.thumbnail((max(w, 20), max(h, 20)))
        return img


# ---------------------------------------------------------------------------
# Manual editing
# ---------------------------------------------------------------------------

MANUAL_PARAMS = [
    ("Brightness", "brightness", ImageEnhance.Brightness),
    ("Contrast", "contrast", ImageEnhance.Contrast),
    ("Saturation", "color", ImageEnhance.Color),
    ("Sharpness", "sharpness", ImageEnhance.Sharpness),
]


def manual_edit(sess: Session):
    values = {"brightness": 1.0, "contrast": 1.0, "color": 1.0, "sharpness": 1.0}
    base = sess.working.copy()
    idx = 0

    def rebuild():
        img = base
        for _, key, cls in MANUAL_PARAMS:
            img = cls(img).enhance(values[key])
        return img

    while True:
        cols, lines = term_size()
        preview_src = rebuild()
        # Reserve rows for: header(8) + blank(1) + one slider row per param
        # + blank(1) + footer(1), so the image never pushes the sliders
        # (or itself) off the visible screen.
        reserved = 8 + 1 + len(MANUAL_PARAMS) + 1 + 1
        image_rows = max(3, lines - reserved)
        rendered = render_image_fit(preview_src, image_rows, max_cols=min(cols - 4, 220))

        print_header("Manual Edit — live preview")
        print(rendered)
        print()
        for i, (label, key, _) in enumerate(MANUAL_PARAMS):
            marker = YELLOW + " ➤ " if i == idx else "   "
            bar_len = 20
            pos = int(max(0, min(2.0, values[key])) / 2.0 * bar_len)
            bar = GREEN + "█" * pos + DIM + GREY + "─" * (bar_len - pos) + RESET
            print(f"{marker}{RESET}{WHITE}{label:<11}{RESET} {bar}  {values[key]:.2f}x")
        print()
        print(
            DIM + GREY
            + "  ↑/↓ choose slider   ←/→ adjust   Enter apply & save to history"
              "   Esc cancel   'r' reset sliders"
            + RESET
        )

        key = get_key()
        if key == "UP":
            idx = (idx - 1) % len(MANUAL_PARAMS)
        elif key == "DOWN":
            idx = (idx + 1) % len(MANUAL_PARAMS)
        elif key == "LEFT":
            k = MANUAL_PARAMS[idx][1]
            values[k] = round(max(0.0, values[k] - 0.05), 2)
        elif key == "RIGHT":
            k = MANUAL_PARAMS[idx][1]
            values[k] = round(min(2.0, values[k] + 0.05), 2)
        elif key in ("r", "R"):
            values = {"brightness": 1.0, "contrast": 1.0, "color": 1.0, "sharpness": 1.0}
        elif key == "ENTER":
            sess.apply(rebuild())
            return
        elif key == "ESC":
            return


# ---------------------------------------------------------------------------
# Image action screen
# ---------------------------------------------------------------------------

def choose_folder():
    folders = candidate_folders()
    folders.append(("Enter custom path", None))
    labels = [f"{name}" for name, _ in folders]
    choice = menu("Where do you want to browse?", labels, subtitle="Browse")
    if choice == -1:
        return None
    name, path = folders[choice]
    if path is None:
        raw = text_prompt("Enter a folder path")
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.exists() or not path.is_dir():
            print(RED + "  That folder doesn't exist." + RESET)
            pause()
            return None
    return path


def choose_image(folder: Path):
    files = list_images(folder)
    if not files:
        print_header("Browse")
        print(RED + f"  No images found in {folder}" + RESET)
        pause()
        return None
    labels = [f.name for f in files]
    choice = menu(f"Images in {folder.name or folder}", labels, subtitle=str(folder))
    if choice == -1:
        return None
    return files[choice]


def preview_extra(img, num_menu_options, has_subtitle=True):
    """Sizes and renders a preview image so it fits ABOVE a menu with
    num_menu_options rows, leaving room for header/title/footer chrome,
    so the whole frame (image + menu) fits in one terminal-height redraw."""
    cols, lines = term_size()
    header_len = 8 if has_subtitle else 7
    chrome = header_len + 2 + 2 + num_menu_options + 2 + 1
    available = max(5, lines - chrome)
    return render_image_fit(img, available, max_cols=min(cols - 4, 220))


def full_preview(img, note=""):
    """A minimal-chrome, near-full-terminal-size preview — use this when
    the small thumbnail next to a menu isn't enough to judge an edit."""
    cols, lines = term_size()
    print_header(note)
    reserved = 8 + 2  # header + blank/footer
    rows = max(6, lines - reserved)
    print(render_image_fit(img, rows, max_cols=min(cols - 2, 220)))
    print()
    print(DIM + GREY + "  Press any key to go back" + RESET)
    get_key()


def filters_menu(sess: Session):
    names = list(FILTERS.keys())
    while True:
        extra = preview_extra(sess.working, len(names), has_subtitle=True)
        choice = menu("Filters — choose a preset", names, subtitle="Filters",
                       footer="↑/↓ move   Enter apply   Esc back", extra=extra)
        if choice == -1:
            return
        fn = FILTERS[names[choice]]
        result = fn(sess.working)
        sess.apply(result)
        confirm_options = ["Apply another filter", "Undo this filter", "Back to image menu"]
        extra2 = preview_extra(sess.working, len(confirm_options), has_subtitle=False)
        again = menu(f"Applied: {names[choice]}. What next?", confirm_options, extra=extra2)
        if again == 1:
            sess.undo()
        if again != 0:
            return


def show_preview(sess: Session, note=""):
    """Standalone full-screen preview (no menu after it). Safe to use on
    its own, e.g. before a pause()."""
    print_header(note or str(sess.path.name))
    print(render_image(sess.preview_copy()))
    print()


def save_flow(sess: Session):
    choice = menu("Save", ["Overwrite original file", "Save as new file", "Cancel"])
    if choice == -1 or choice == 2:
        return
    if choice == 0:
        try:
            sess.working.save(sess.path)
            sess.dirty = False
            print(GREEN + f"\n  Saved to {sess.path}" + RESET)
        except Exception as e:
            print(RED + f"\n  Error saving: {e}" + RESET)
        pause()
        return
    default_name = sess.path.stem + "_edited" + sess.path.suffix
    name = text_prompt("New filename", default_name)
    if not name:
        return
    new_path = sess.path.parent / name
    try:
        sess.working.save(new_path)
        print(GREEN + f"\n  Saved to {new_path}" + RESET)
    except Exception as e:
        print(RED + f"\n  Error saving: {e}" + RESET)
    pause()


def delete_flow(sess: Session):
    confirm = menu(f"Delete {sess.path.name}? This cannot be undone.", ["Cancel", "Yes, delete it"])
    if confirm == 1:
        try:
            sess.path.unlink()
            print(RED + f"\n  Deleted {sess.path}" + RESET)
            pause()
            return True
        except Exception as e:
            print(RED + f"\n  Error deleting: {e}" + RESET)
            pause()
    return False


def rename_flow(sess: Session):
    new_name = text_prompt("New file name (with extension)", sess.path.name)
    if not new_name or new_name == sess.path.name:
        return
    new_path = sess.path.parent / new_name
    try:
        os.rename(sess.path, new_path)
        sess.path = new_path
        print(GREEN + f"\n  Renamed to {new_path.name}" + RESET)
    except Exception as e:
        print(RED + f"\n  Error renaming: {e}" + RESET)
    pause()


def image_menu(path: Path):
    sess = Session(path)
    while True:
        options = [
            "View full-size preview",
            "Filters (preset profiles)",
            "Manual edit (brightness / contrast / saturation / sharpness)",
            f"Undo{' (' + str(len(sess.history)) + ')' if sess.history else ''}",
            "Reset to original",
            "Save",
            "Rename",
            "Delete",
            "Back to file list",
        ]
        extra = preview_extra(sess.working, len(options), has_subtitle=True)
        choice = menu("Editing: " + path.name, options, subtitle=str(path), extra=extra)
        if choice in (-1, 8):
            if sess.dirty:
                c = menu("You have unsaved changes. Leave anyway?", ["Go back and save", "Discard changes and leave"])
                if c == 0:
                    continue
            return
        elif choice == 0:
            full_preview(sess.working, note=path.name)
        elif choice == 1:
            filters_menu(sess)
        elif choice == 2:
            manual_edit(sess)
        elif choice == 3:
            if not sess.undo():
                print(RED + "\n  Nothing to undo." + RESET)
                pause()
        elif choice == 4:
            sess.reset()
        elif choice == 5:
            save_flow(sess)
        elif choice == 6:
            rename_flow(sess)
        elif choice == 7:
            if delete_flow(sess):
                return


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    _enable_windows_ansi()
    try:
        while True:
            choice = menu(
                "Main Menu",
                ["Browse for an image", "About", "Quit"],
                subtitle="A portable terminal image editor",
            )
            if choice in (-1, 2):
                clear()
                print(CYAN + "  Thanks for using Pixel Forge. Catch you next time.\n" + RESET)
                break
            elif choice == 0:
                folder = choose_folder()
                if folder is None:
                    continue
                while True:
                    img_path = choose_image(folder)
                    if img_path is None:
                        break
                    image_menu(img_path)
            elif choice == 1:
                print_header("About")
                print(WHITE + "  Pixel Forge - a self-contained terminal image editor." + RESET)
                print(WHITE + "  Runs anywhere Python + Pillow is available, USB stick included." + RESET)
                print(WHITE + "  Arrow keys + Enter to navigate. Build 1.3" + RESET)
                pause()
    except KeyboardInterrupt:
        print(RESET)
        print("\nInterrupted.")


if __name__ == "__main__":
    main()