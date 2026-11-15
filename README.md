# S67 küte

Electricity-price-aware heating for S67, built on Apple Shortcuts, Tuya scenes and a Scriptable widget.

- `tools/` – Python that generates the shortcuts (`_head.py`, `_mid.py`, `_tail.py` → `build.py`), a simulator and tests.
- `Küte täna.js` – Scriptable widget showing today's plan and current status.
- `SETUP.md` – setup, settings and how it all works.
- `build/orig/Shortcut.wflow` – the original shortcut the Tuya scene actions are copied from.

Build and sign:

```bash
cd tools && cat _head.py _mid.py _tail.py > build.py && python3 build.py
shortcuts sign -m anyone -i "build/S67 Küte (uus).wflow" -o "S67 Küte (uus).shortcut"
```
