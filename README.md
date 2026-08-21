# Pixel Forge

A self-contained, portable, terminal-based image editor. Old-school
arrow-key + Enter menus, a colored ASCII banner, and your actual photos
rendered in full color right inside the terminal - no GUI, no Image Editors,
no internet required.

## What it does

- Scans your **Pictures**, **Downloads**, **Desktop**, **Documents**, and
  current folder for images (png/jpg/jpeg/bmp/gif/webp/tiff)
- Renders the selected image **in the terminal**, in full RGB color,
  using an ANSI "half-block" trick (two pixels per character cell) -
  works in Windows Terminal, PowerShell, cmd.exe (with ANSI enabled
  automatically), and any Linux/Mac terminal
- **Filters**: Warm, Cool, Sunny, Noir, Vintage/Sepia, Vivid, Grayscale
- **Manual edit**: brightness, contrast, saturation, sharpness - with a
  **live preview** that updates as you nudge sliders with ←/→
- **Undo**, **Reset to original**, **Save** (overwrite or save-as),
  **Rename**, **Delete**
- Navigate everything with **arrow keys + Enter**, just like an old
  console game menu - a `➤` cursor shows your selection

## Requirements

- Python 3.8+
- Pillow (the only dependency)

## Setup

```bash
pip install -r requirements.txt
python app.py
```

On Windows, you can also just:

```
pip install Pillow
python app.py
```

## Carrying it on a USB drive

The script itself (`app.py`) is fully portable - just Python code. The
only thing that isn't "in the box" by default is Pillow itself, since
it has compiled components. Two good options if you want a fully
offline, drop-anywhere setup:

1. **Portable Python + pre-installed Pillow**: grab a portable Python
   build (e.g. from python.org's embeddable zip, or WinPython), unzip
   it onto the USB drive alongside `app.py`, and `pip install Pillow`
   into that portable interpreter's `site-packages`. Then the whole
   thing runs standalone on any Windows machine, no install required.

2. **Bundle it as a single .exe** with PyInstaller on your own machine:
   ```
   pip install pyinstaller
   pyinstaller --onefile app.py
   ```
   Drop the resulting `dist/app.exe` on the USB drive. This is the
   simplest "just double-click it" option for Windows laptops that
   already have nothing installed.

Either way, none of your images ever leave the machine - everything is
local file I/O, no network calls at all.

## Controls

- **↑ / ↓** - move the cursor in any menu
- **← / →** - adjust sliders in Manual Edit
- **Enter** - select / apply
- **Esc** - go back
- In Manual Edit: **r** resets all sliders to 1.00x

## Notes on the terminal preview

The image preview uses Unicode `▀` (upper half block) characters with
independently colored foreground/background per cell, which gives you
roughly double the vertical resolution of one-color-per-character
ASCII art. It's not a substitute for a real image viewer, but it's
more than enough to judge a filter or edit at a glance. If your
terminal font/theme doesn't support true 24-bit color, the preview
will look posterized/limited - this is a terminal limitation, not a
bug in the script.

## Extending it

Everything filter-related lives in the `FILTERS` dict and the
`apply_*` functions near the top of `app.py` - add a new function that
takes and returns a Pillow `Image` and drop it in the dict to add a
new preset.
