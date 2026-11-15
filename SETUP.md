# Küte – setup guide

Four shortcuts replace the price logic of your current **S67 Küte**. The old shortcut is untouched; keep it until the new setup has run well for a few days.

| Shortcut | What it does | Runs |
|---|---|---|
| **Kyte seaded** | Holds all settings. Edit values here. | Called by the others |
| **Küte plaan** | Downloads Elering prices and the weather forecast. Plans OFF / ON / HI for every hour until the end of tomorrow. Saves the plan and creates approval reminders. | Automation 15:00 |
| **S67 Küte (uus)** | Reads this hour from the plan and runs the Tuya scene. | Automation every hour |
| **Küte valik** | Manual menu to answer an approval question. | By hand (also on Apple Watch) |
| **Kyte test run** | Optional. Shows what S67 Küte (uus) would do this hour, without switching anything. | By hand |

The settings shortcut is called **Kyte** seaded, with a plain *y*. *Run Shortcut* couldn't find the name with *ü* on the device.

## 1. Remove the earlier versions

Delete these shortcuts before importing. If they stay, the new copies are imported as "Küte plaan 2" and so on, and the links between them break.

- Küte seaded, Küte plaan, S67 Küte (uus), Küte valik (the previous version, which froze)
- Kyte probe, Kyte probe 2, Kyte probe 3 (test shortcuts, no longer needed)

If an hourly automation already runs **S67 Küte (uus)**, it loses its shortcut when you delete it. Point it at the new one after importing (step 3).

## 2. Import

1. AirDrop the `.shortcut` files to your iPhone, or open them on the Mac. Import **Kyte seaded** first.
2. **Kyte seaded** asks for your latitude and longitude. The defaults are central Tallinn. Write them with a dot, e.g. `59.437`.
3. **S67 Küte (uus)** asks you to pick the three Tuya scenes: Küte-off, Küte-on and Küte-on-HI.
4. Allow access when asked: Reminders, files in iCloud Drive, and the dashboard.elering.ee and api.open-meteo.com websites.

## 3. Automations (Shortcuts → Automation)

1. **Time of day 15:00, daily**, run immediately → *Run Shortcut* **Küte plaan**. The 00:00 automation is no longer needed. If you made one, delete it.
2. Your hourly automations: make them run **S67 Küte (uus)** instead of **S67 Küte**. Two shortcuts must never switch the heating in the same hour.
3. Run **Küte plaan** once by hand right after setup, so a plan exists before the next full hour.

**Run it from the tile, not the editor.** Tap the shortcut in the Shortcuts list. Running it from inside the editor is many times slower, because the editor shows every step as it runs.

**Tuya:** set the Küte-on-HI scene to 24 °C, as you planned. Also check that Küte-off keeps a 16 °C safety floor. The thermostat should never be fully off: if the phone is offline or a shortcut fails, the scene that last ran stays in effect.

## 4. How it decides

- **Expensive hours:** price incl. VAT is above `off_above` → OFF.
- **Very cheap hours:** below `hi_below` → HI. During quiet hours (00–06) a cheap price gives only ON, so you don't sleep in a hot room. HI starts at 06 to preheat for the morning.
- **Preheating:** up to `preheat_hours` before an expensive block, an hour that is clearly cheaper runs HI. Only before blocks of at least `preheat_min_block` hours, and only in hours whose own price is at most `preheat_max_price`. A single expensive hour is just OFF.
- **Waiting:** an ON hour is skipped when the next hour is much cheaper.
- **Long expensive blocks:** the planner estimates how fast the house cools from the forecast night minimum and `loss_factor`. To keep you above `t_floor`, it adds back the cheapest hours inside the block.
- **Approval:** if those added hours cost more than `ask_above` s/kWh, they need your OK. This doesn't apply on extremely cold days (≤ `ask_never_below`); those hours run without asking.
- **No plan:** if the plan is missing or doesn't cover this hour, S67 Küte (uus) decides from the live price like the old shortcut. The notification then says `otse hinnast (plaani pole)`.

## 5. Answering an approval question

At 15:00, **Küte plaan** creates a reminder like this:

> Küte 20.01.26: 16 h väljas. Kas kütan 7 h (07, 08, 10, 13, 14, 17, 19) à 36.01 s/kWh ≈ 12.61 €? (tehtuks = jah, kustuta = ei)

| You do | Result |
|---|---|
| **Complete** the reminder | Yes: all those hours heat |
| **Delete** the reminder | No: none of them heat |
| **Leave it** | `ask_default` applies (OFF unless you change it) |
| Run **Küte valik** | Pick *Küta kõik* / *Küta ainult 1 odavaim tund* / *Ära küta* / *Tühista valik*, then *Täna* or *Homme*. This overrides the reminder. *Tühista* goes back to the reminder. |

You can change your answer at any time. Each hour reads it again. If you run Küte plaan again on the same day, it doesn't ask twice about a day it has already asked about.

## 6. Settings (Kyte seaded)

Open **Kyte seaded** and change the values. Each value has a comment above it explaining what it does. Most used:

| Setting | Default | Meaning |
|---|---|---|
| `enabled` | true | `false` = the hourly shortcut does nothing (manual control) |
| `notifications` / `plan_notification` | true | Hourly notification / 15:00 "Küte homme" summary |
| `travel_mode` | false | `true` = OFF in every hour except when the spot price incl. VAT is below `travel_on_below`. No approval reminders. See *Travelling* below. |
| `travel_on_below` | 3 | Travel mode heats (ON) only below this price, s/kWh |
| `off_above` / `hi_below` | 15 / 5 | Spot price limits incl. VAT, s/kWh |
| `quiet_start` / `quiet_end` | 0 / 6 | No HI in these hours |
| `preheat_hours` | 2 | How far ahead to preheat |
| `preheat_min_gap` | 7 | Preheat hour must be this much cheaper than the expensive block (incl. network fee) |
| `preheat_min_block` | 2 | Shortest expensive block worth preheating for, in hours |
| `preheat_max_price` | 12 | Highest spot price incl. VAT at which an hour may preheat |
| `t_floor` | 19 | Lowest acceptable indoor °C during long expensive periods |
| `loss_factor` | 32 | ≈ 1 °C/h at −10 °C outside. Lower it if the house cools faster. |
| `ask_above` | 25 | Price (incl. network fee) above which comfort hours need approval |
| `ask_default` | OFF | What happens to an unanswered approval question |
| `kwh_per_hour` | 5 | Used only for the € estimates |
| `net_day` / `net_night`, `vat`, `holidays` | | Network fee rates, VAT and holiday dates for the network fee. Add moving holidays (Good Friday) as `yyyy-MM-dd`. |

Numbers are stored as numbers, so the comma or dot your phone uses doesn't matter. Tap a number to change it.

## 7. Files

The shortcuts keep their data in **iCloud Drive → Shortcuts**:

- `kyte-plan.json`: the current plan. Each hour is stored as `mode|reason|price|day`.
- `kyte-state.json`: the days already asked about
- `kyte-valik.json`: your Küte valik answers
- `kyte-praegu.json`: what S67 Küte (uus) did in the last hour (mode, reason, price, travel mode), for the widget

You can delete any of them at any time. Delete `kyte-plan.json` from the previous version once; its format changed. If it stays, the new version doesn't find any hours in it and decides from the live price until the next 15:00 run.

### Travelling

All shortcuts now work in **Tallinn time**, wherever the phone is. Plan hours, the network fee's day rate, quiet hours, approval dates and Küte valik's *Täna* / *Homme* all follow the house's clock. They no longer follow the phone's clock. In the simulator the plan came out identical with the phone set to London, New York, Los Angeles, Kolkata, Tokyo and Auckland.

Two things to know:

- Automations fire at the phone's local time. The hourly one is fine anywhere. But when you're **east** of Estonia, 15:00 on the phone comes before 15:00 in Tallinn, when tomorrow's prices may not be out yet. While you're there, move the Küte plaan automation later by the time difference (e.g. 21:00 in Bangkok). West of Estonia nothing needs changing.
- On the few days when Estonia and the other country change their clocks on different dates, a plan made abroad can be off by one hour.

**Travel mode.** In Kyte seaded set `travel_mode` to `true`. From the next full hour, the heating is OFF except in hours whose spot price incl. VAT is below `travel_on_below` (3 s/kWh), which run ON. There are no approval reminders. Set it back to `false` when you're home. Make sure your thermostats' frost protection is on, because in travel mode the house can go a long time without heat.

## 8. What changed in this version

- **Tallinn time and travel mode (22.10.):** see *Travelling* above. Kyte test run's output now ends with the Tallinn time it used. S67 Küte (uus) writes `kyte-praegu.json` for the widget. Re-import all five shortcuts. An older Kyte seaded without the travel settings works: travel mode stays off.

- **Less preheating (22.10.):** no preheating before a single expensive hour, and none in hours that are themselves above `preheat_max_price`. New settings `preheat_min_block` and `preheat_max_price`. An older Kyte seaded without them uses 2 and 12.

- **Faster:** a plan now takes about 1,800–3,200 steps (the previous version took about 5,000). The hourly shortcut takes about 100.
- **No more "Please choose a value for each parameter":** text conditions on values read from a dictionary now carry an explicit text type. This was the crash in your screenshot.
- **Decimals:** the settings and the VAT calculation no longer depend on the phone's decimal separator. The earlier version read `4.58` as 0 on a phone that uses a comma.
- **Prices read in any order:** the phone may reorder the fields of the Elering answer. The first import on the Mac then wrote a plan with no hours. Both the plan and the live-price fallback now read prices whatever the order. If the hours still can't be read, Küte plaan shows a warning instead of saving an empty plan.
- **Every hour planned:** on the device, *Adjust Date* ignores a number of hours taken from a variable. Every hour got the same key, so the plan held only one hour. The planner now steps the date forward one hour at a time.
- **No plan file:** Kyte test run and S67 Küte (uus) no longer stop with "item 2, but the list only has 1" when the plan is missing or doesn't cover this hour.
- I tested it in a simulator against a reference model on 7 days (autumn, winter cold snaps, both DST changes) and in 18 hourly cases. I haven't run it on your iPhone yet.

## Home-screen widget: Küte täna (Scriptable)

`Küte täna.js` shows **Küte praegu** (what the heating is doing now: On ✅, Off ❌, Huugab 🔥, or ❓ Asks for an unanswered approval hour), today's average spot price incl. VAT, the peak hour and the planner's blocks (OFF ❄️ Cold, ON 🍃 Regular, HI 🔥 Hot, unanswered approval ❓ Asks).

1. Install **Scriptable** from the App Store.
2. In Scriptable tap **+**, paste the whole of `Küte täna.js` and name the script **Küte täna**.
3. In Scriptable go to **Settings → File Bookmarks → +**, choose **Pick Folder**, select **iCloud Drive → Shortcuts** and name the bookmark exactly **Shortcuts**.
4. On the home screen add a **Scriptable** widget (medium recommended). Long-press it, then **Edit Widget → Script: Küte täna**. Lock-screen widgets work the same way.
5. Optional: in your morning automation add Scriptable's **Run Script** action (Script: Küte täna). It refreshes the widget's data and returns the summary as text, which you can pass to **Show Notification**.

The widget reads `kyte-plan.json` itself, so it's correct even if the automation doesn't run. It refreshes about once an hour, highlights the current block and dims past ones. Küte plaan replaces the plan at 15:00, so the script keeps today's morning hours in its own cache.

*Küte praegu* comes from `kyte-praegu.json` once S67 Küte (uus) has run this hour. Before that, it comes from the plan. In travel mode the label reads *Küte praegu · ✈️ travel*, and the blocks and bars show the travel-mode hours. The widget always shows Tallinn's day and hour, also when the phone is abroad.
