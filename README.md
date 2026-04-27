# MarqueeBackdrops

A Nuke tool that lets you draw a **backdrop by dragging a marquee** directly in the Node Graph — the same way you'd draw a selection — rather than placing a node and resizing it manually.

![Nuke Version](https://img.shields.io/badge/Nuke-11%2B-lightgrey) ![PySide](https://img.shields.io/badge/PySide-2%20%7C%206-blue) ![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Drag to place** — press `Shift+B`, click and drag a rectangle, release to create
- **Random pastel colours** — each backdrop gets a unique, easy-on-the-eye colour automatically
- **Label prompt** — optionally name the backdrop immediately after drawing
- **Wrap selected nodes** — toolbar button creates a backdrop sized around your current selection
- **Cross-version** — works on Nuke 11 through 16+ (PySide2 and PySide6)
- **Cross-platform** — Windows; Linux and macOS compatible

---

## Requirements

| Nuke | Qt binding |
|------|-----------|
| 11 – 14.x | PySide2 (bundled) |
| 15 – 16+ | PySide6 (bundled) |

No third-party packages required.

---

## Installation

1. Copy `marquee_backdrop.py` into `~/.nuke/`
2. Add the following to `~/.nuke/menu.py`:

```python
# menu.py - add these lines to your existing ~/.nuke/menu.py
# Compatible with Nuke 11-14.x (PySide2) and Nuke 15-16+ (PySide6)

import nuke
import marquee_backdrop

# Toolbar button to create a backdrop around selected nodes
toolbar = nuke.toolbar("Nodes")
toolbar.addCommand(
    "Other/Backdrop (Marquee)",
    "marquee_backdrop.create_backdrop_around_selected()",
    "",
    icon="Backdrop.png",
)
```

That's it. Restart Nuke (or run `marquee_backdrop.install()` from the Script Editor to load without restarting).

---

## Usage

### Draw a backdrop
1. Click in the Node Graph to make sure it has focus
2. Press **`Shift+B`** — the cursor becomes a crosshair
3. **Click and drag** to draw your rectangle
4. Release — a label dialog appears, type a name and hit Enter (or cancel to leave it blank)

> Press `Escape` or right-click at any point to cancel.

### Wrap selected nodes
Select one or more nodes, then click **Other → Backdrop (Marquee)** in the Nodes toolbar. A backdrop is created with padding around the selection.

---

## Configuration

At the top of `marquee_backdrop.py`:

```python
ASK_LABEL     = True    # Show label dialog after drawing
RANDOM_COLOUR = True    # Auto-assign a random pastel colour
DEFAULT_COLOR = 0x6A6A6AFF  # Fallback colour when RANDOM_COLOUR = False
DEBUG         = False   # Print [MB] trace lines to the Script Editor
```

---

## File Structure

```
MarqueeBackdrops/
├── src/
│   ├── marquee_backdrop.py   # Main tool — copy this to ~/.nuke/
│   └── menu.py               # Example menu.py snippet
├── README.md
└── LICENSE
```

---

## License

MIT — see [LICENSE](LICENSE).
