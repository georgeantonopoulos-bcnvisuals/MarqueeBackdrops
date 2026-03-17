# menu.py — add these lines to your existing ~/.nuke/menu.py
# ─────────────────────────────────────────────────────────────
# Compatible with Nuke 11–14.x (PySide2) and Nuke 15+ (PySide6)

import marquee_backdrop

# Toolbar button to create a backdrop around selected nodes
toolbar = nuke.toolbar("Nodes")
toolbar.addCommand(
    "Other/Backdrop (Marquee)",
    "marquee_backdrop.create_backdrop_around_selected()",
    "shift+b",
    icon="Backdrop.png",
)
