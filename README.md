# S67 küte

Electricity-price-aware heating for S67, built on Apple Shortcuts, Tuya scenes and a Scriptable widget.

- `tools/` – Python that generates the shortcuts (`_head.py`, `_mid.py`, `_tail.py` → `build.py`), a simulator and tests.
- `Küte täna.js` – Scriptable widget showing today's plan and current status.
- `shortcuts/` – signed, ready-to-import shortcuts (latest build).
- `SETUP.md` – setup, settings and how it all works.
- `build/orig/Shortcut.wflow` – the original shortcut the Tuya scene actions are copied from.

## Setup

Full details, settings and how the plan is made: [SETUP.md](SETUP.md).

**1. Tuya.** You need three scenes in the Tuya app: **Küte-off** (keep a 16 °C floor), **Küte-on** and **Küte-on-HI** (24 °C).

**2. Import the shortcuts** from [`shortcuts/`](shortcuts) to your iPhone (download each, or AirDrop from a Mac). If older versions exist, delete them first, or choose **Replace**.
1. **Kyte seaded** first. It asks for your latitude and longitude, written with a dot (e.g. `59.437`).
2. **Küte plaan**, **S67 Küte (uus)**, **Küte valik** and **Kyte test run**. S67 Küte (uus) asks you to pick the three Tuya scenes.
3. Allow access when asked: Reminders, iCloud Drive files, `dashboard.elering.ee` and `api.open-meteo.com`.

**3. Automations** (Shortcuts → Automation, set each to run immediately):
- **Daily at 15:00** → Run Shortcut **Küte plaan**.
- **Every hour** → Run Shortcut **S67 Küte (uus)**. Only one shortcut may switch the heating each hour, so turn off any old hourly automation.

**4. First run.** Run **Küte plaan** once by hand, then **Kyte test run** to see what this hour would do without switching anything. Run them from the tile, not the editor; the editor is much slower.

**5. Widget (optional).**
1. Install **Scriptable**, tap **+**, paste [`Küte täna.js`](Küte%20täna.js) and name it **Küte täna**.
2. Scriptable → Settings → File Bookmarks → **+** → Pick Folder → **iCloud Drive → Shortcuts**, named exactly **Shortcuts**.
3. Add a Scriptable widget (medium works best), then Edit Widget → Script: **Küte täna**.

**Day to day.** When some expensive hours need heating anyway, Küte plaan creates a reminder: complete it to approve, delete it to decline, or use **Küte valik**. Settings, including **travel mode** (`travel_mode` = `true` heats only below `travel_on_below` s/kWh), are changed in **Kyte seaded**.

## Development

Build and sign:

```bash
cd tools && cat _head.py _mid.py _tail.py > build.py && python3 build.py
shortcuts sign -m anyone -i "build/S67 Küte (uus).wflow" -o "S67 Küte (uus).shortcut"
```
