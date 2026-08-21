# Pixel Forge

A self-contained, portable, terminal-based image editor. Old-school
arrow-key + Enter menus, a colored ASCII banner, and your actual photos
rendered in full color right inside the terminal - no GUI,
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

## Carrying it on a USB drive / giving it to non-technical people

The script itself (`app.py`) is just Python code, but for someone who
doesn't have Python installed and shouldn't have to, package it into a
single **`PixelForge.exe`** that runs by double-clicking - no install,
no terminal commands, no Python knowledge required from them.

### Option A - you have a Windows machine

```
pip install -r requirements.txt
pip install pyinstaller
pyinstaller build.spec
```

The finished exe lands at `dist\PixelForge.exe`. Copy just that one
file anywhere - USB stick, another PC, wherever. That's the whole
deliverable; nothing else needs to travel with it.

### Option B - you *don't* have a Windows machine

PyInstaller has to build on the same OS as its target, so building a
`.exe` from Mac/Linux directly isn't reliable. Instead, this repo
includes a GitHub Actions workflow (`.github/workflows/build.yml`)
that builds it for you on a real, free Windows machine in the cloud:

1. Push this folder to a GitHub repo (public or private, doesn't
   matter - a private repo works fine and free Actions minutes still
   apply).
2. GitHub builds it automatically on every push to `main`. To trigger
   it by hand instead, go to the repo's **Actions** tab → **Build
   Windows EXE** → **Run workflow**.
3. When the run finishes (a couple minutes), open that run and
   download the **PixelForge-windows** artifact - it's a zip
   containing `PixelForge.exe`.
4. Hand that exe to whoever needs it. They just double-click it; no
   install step, no command line, no Python.

### What the person receiving the exe actually experiences

- Double-click `PixelForge.exe`
- A black console window opens with the colored banner and menu
- Arrow keys + Enter to navigate, exactly as described below
- If Windows SmartScreen warns about an "unrecognized publisher"
  (normal for an exe that isn't code-signed by a paid certificate),
  they click **More info → Run anyway**
- Nothing gets installed, no files are written anywhere except the
  images they choose to edit/save - closing the window removes any
  trace of it ever running

None of this touches the network - everything is local file I/O, so
photos never leave the machine either way (script or exe).

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
