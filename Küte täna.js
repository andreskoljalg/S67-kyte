// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: orange; icon-glyph: fire;

// Küte täna: today's heating plan from kyte-plan.json as a widget.
// Needs a Scriptable File Bookmark named "Shortcuts" that points to iCloud Drive/Shortcuts.
// Run from a shortcut (Scriptable's "Run Script" action) it returns the same summary as text.
// Always in Tallinn time, like the shortcuts, so it shows the house's day when the phone is abroad.

const BOOKMARK = "Shortcuts"
const CACHE = "kyte-tana-cache.json"

const MODES = {
  OFF: { icon: "❄️", label: "Cold", color: Color.dynamic(new Color("#0a6fd6"), new Color("#64b5ff")), bar: "#0a84ff" },
  ON: { icon: "🍃", label: "Regular", color: Color.dynamic(new Color("#1e8e3e"), new Color("#5fd47e")), bar: "#30d158" },
  HI: { icon: "🔥", label: "Hot", color: Color.dynamic(new Color("#d0281b"), new Color("#ff6b5e")), bar: "#ff453a" },
  ASK: { icon: "❓", label: "Asks", color: Color.dynamic(new Color("#8e44ad"), new Color("#d39bff")), bar: "#bf5af2" },
}
const TEXT = Color.dynamic(new Color("#1c1c1e"), new Color("#f2f2f7"))
const DIM = Color.dynamic(new Color("#8a8a8e"), new Color("#8e8e93"))
const BG = Color.dynamic(new Color("#ffffff"), new Color("#1c1c1e"))

// What S67 Küte did this hour, from kyte-praegu.json
const STATUS = {
  OFF: { text: "Off ❌", color: MODES.OFF.color },
  ON: { text: "On ✅", color: MODES.ON.color },
  HI: { text: "Huugab 🔥", color: MODES.HI.color },
  ASK: { text: "Asks ❓", color: MODES.ASK.color },
}

const pad = n => String(n).padStart(2, "0")

// Date and hour in Tallinn: {date: "yyyy-MM-dd", hour, key: "yyyy-MM-ddTH"} like the plan's keys
function tallinn(d) {
  let p
  try {
    p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Tallinn", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
    }).formatToParts(d).map(x => [x.type, x.value]))
  } catch (e) {
    p = { year: d.getFullYear(), month: pad(d.getMonth() + 1), day: pad(d.getDate()), hour: d.getHours() }
  }
  const date = `${p.year}-${p.month}-${p.day}`, hour = parseInt(p.hour, 10) % 24
  return { date, hour, key: `${date}T${hour}` }
}
const num = s => parseFloat(String(s).replace(",", "."))
const fmt = n => n.toFixed(2)

async function readJSON(fm, path) {
  if (!fm.fileExists(path)) return null
  if (!fm.isFileDownloaded(path)) await fm.downloadFileFromiCloud(path)
  try { return JSON.parse(fm.readString(path)) } catch (e) { return null }
}

// Today's hours as {hour: "MODE|why|price|day"}. The planner replaces the plan at 15:00 with
// hours from then on, so the morning hours are kept in a local cache for the rest of the day.
async function loadToday(now) {
  const today = tallinn(now).date
  const local = FileManager.local()
  const cachePath = local.joinPath(local.documentsDirectory(), CACHE)
  let cache = null
  if (local.fileExists(cachePath)) {
    try { cache = JSON.parse(local.readString(cachePath)) } catch (e) {}
  }
  const hours = cache && cache.date === today ? cache.hours : {}

  const fm = FileManager.iCloud()
  if (!fm.bookmarkExists(BOOKMARK)) return { error: `Add a File Bookmark named "${BOOKMARK}" in Scriptable settings.` }
  const dir = fm.bookmarkedPath(BOOKMARK)
  const plan = await readJSON(fm, fm.joinPath(dir, "kyte-plan.json")) || {}
  for (let h = 0; h < 24; h++) {
    const v = plan[`${today}T${h}`]
    if (v) hours[h] = v
  }
  local.writeString(cachePath, JSON.stringify({ date: today, hours }))

  const valik = (await readJSON(fm, fm.joinPath(dir, "kyte-valik.json")) || {})[today]
  // trusted for this hour and the last one, so a run a few minutes late does not blank the status
  const st = await readJSON(fm, fm.joinPath(dir, "kyte-praegu.json"))
  const fresh = st && [tallinn(now).key, tallinn(new Date(now.getTime() - 3600e3)).key].includes(st.t)
  const travel = fresh && st.travel === "true" ? num(st.tb) : null
  const ran = st && st.t === tallinn(now).key ? st : null
  return { hours, valik, travel, ran }
}

// Approval hours as the hourly run would treat them: a Küte valik answer decides, otherwise "Asks".
function shownMode(mode, valik) {
  if (!mode.startsWith("ASK")) return mode
  if (valik === "all") return "ON"
  if (valik === "one") return mode === "ASK1" ? "ON" : "OFF"
  if (valik === "none") return "OFF"
  return "ASK"
}

// travel: the travel_on_below price while travel mode is on, otherwise null
function summarize(hours, valik, travel) {
  const list = []
  for (let h = 0; h < 24; h++) {
    if (!hours[h]) continue
    const [mode, , price] = hours[h].split("|")
    const p = num(price)
    list.push({ h, mode: travel === null ? shownMode(mode, valik) : p < travel ? "ON" : "OFF", price: p })
  }
  if (!list.length) return null
  const avg = list.reduce((a, x) => a + x.price, 0) / list.length
  const peak = list.reduce((a, x) => (x.price > a.price ? x : a))
  const blocks = []
  for (const x of list) {
    const last = blocks[blocks.length - 1]
    if (last && last.mode === x.mode && last.end === x.h) last.end = x.h + 1
    else blocks.push({ start: x.h, end: x.h + 1, mode: x.mode })
  }
  return { avg, peak, blocks, list, count: list.length, first: list[0].h }
}

// Küte praegu: what the hourly run switched to this hour, or the plan's hour when it has not run yet
function currentStatus(data, s, hour) {
  const planned = s && s.list.find(x => x.h === hour)
  const mode = data.ran ? data.ran.mode : planned ? planned.mode : null
  if (!STATUS[mode]) return { text: "–", color: DIM, travel: data.travel != null }
  return { ...STATUS[mode], mode, travel: data.travel != null }
}

const span = b => `${pad(b.start)}–${pad(b.end % 24)}`

function asText(s, st) {
  const lines = [`Küte praegu: ${st.text}${st.travel ? " (travel mode)" : ""}`,
    `Average price today: ${fmt(s.avg)} s/kWh`, `Peak: ${pad(s.peak.h)}:00 · ${fmt(s.peak.price)} s/kWh`]
  if (s.count < 24) lines.push(`(only ${s.count} hours in the plan)`)
  lines.push("")
  for (const b of s.blocks) lines.push(`${span(b)}  ${MODES[b.mode].icon} ${MODES[b.mode].label}`)
  return lines.join("\n")
}

function addText(stack, str, font, color) {
  const t = stack.addText(str)
  t.font = font
  t.textColor = color
  t.lineLimit = 1
  return t
}

// Past blocks are dimmed and dropped first when the widget has no room for all of them.
function visibleBlocks(blocks, hour, room) {
  let list = blocks
  while (list.length > room && list[0].end <= hour) list = list.slice(1)
  return { list: list.slice(0, room), more: Math.max(list.length - room, 0) }
}

function addBlocks(stack, blocks, hour, room, size) {
  const { list, more } = visibleBlocks(blocks, hour, room)
  for (const b of list) {
    const m = MODES[b.mode]
    const now = b.start <= hour && hour < b.end
    const row = stack.addStack()
    row.centerAlignContent()
    const color = b.end <= hour ? DIM : now ? m.color : TEXT
    addText(row, span(b), now ? Font.boldMonospacedSystemFont(size) : Font.regularMonospacedSystemFont(size), color)
    row.addSpacer(6)
    addText(row, `${m.icon} ${m.label}`, now ? Font.boldSystemFont(size) : Font.systemFont(size), color)
    stack.addSpacer(2)
  }
  if (more) addText(stack, `+${more} more`, Font.systemFont(size - 2), DIM)
}

// 24 price bars coloured by mode, past hours faded, a tick under the current hour.
// Drawn as an image, so it uses fixed colours that read on both light and dark backgrounds.
function chart(s, hour, W, H) {
  const ctx = new DrawContext()
  ctx.size = new Size(W, H)
  ctx.opaque = false
  ctx.respectScreenScale = true
  const labelH = 11, barH = H - labelH - 3, slot = W / 24, gap = Math.max(1, slot * 0.18)
  const lo = Math.min(0, ...s.list.map(x => x.price))
  const hi = Math.max(...s.list.map(x => x.price), lo + 1)
  for (const x of s.list) {
    const h = Math.max(2, ((x.price - lo) / (hi - lo)) * barH)
    ctx.setFillColor(new Color(MODES[x.mode].bar, x.h < hour ? 0.35 : 1))
    const path = new Path()
    path.addRoundedRect(new Rect(x.h * slot + gap / 2, barH - h, slot - gap, h), 1.5, 1.5)
    ctx.addPath(path)
    ctx.fillPath()
  }
  ctx.setFillColor(new Color("#8e8e93"))
  ctx.fillRect(new Rect(hour * slot + gap / 2, barH + 1, slot - gap, 2))
  ctx.setFont(Font.mediumSystemFont(9))
  ctx.setTextColor(new Color("#8e8e93"))
  for (const h of [0, 6, 12, 18]) ctx.drawText(pad(h), new Point(h * slot + gap / 2, barH + 3))
  ctx.setTextAlignedRight()
  ctx.drawTextInRect("24", new Rect(W - 30, barH + 3, 30, labelH))
  return ctx.getImage()
}

function statusLines(stack, st, size) {
  addText(stack, st.travel ? "Küte praegu · ✈️ travel" : "Küte praegu", Font.mediumSystemFont(size <= 18 ? 10 : 11), DIM)
  addText(stack, st.text, Font.boldSystemFont(size), st.color)
}

function header(stack, s, st, big) {
  statusLines(stack, st, big ? 22 : 17)
  stack.addSpacer(4)
  addText(stack, "Average today", Font.mediumSystemFont(11), DIM)
  addText(stack, `${fmt(s.avg)} s/kWh`, Font.boldSystemFont(big ? 22 : 17), TEXT)
  stack.addSpacer(4)
  addText(stack, "Peak", Font.mediumSystemFont(11), DIM)
  addText(stack, `${pad(s.peak.h)}:00 · ${fmt(s.peak.price)}`, Font.semiboldSystemFont(big ? 15 : 13), MODES.HI.color)
  if (s.count < 24) addText(stack, `${s.count} h in plan`, Font.systemFont(10), DIM)
}

function buildWidget(s, st, error, now, family) {
  const w = new ListWidget()
  const hour = tallinn(now).hour
  // Tallinn hours start on whole UTC hours
  w.refreshAfterDate = new Date(Math.floor(now.getTime() / 3600e3) * 3600e3 + 3630e3)

  if (family === "accessoryInline" || family === "accessoryRectangular" || family === "accessoryCircular") {
    if (!s) { w.addText(error || "No plan for today"); return w }
    const cur = s.blocks.find(b => b.start <= hour && hour < b.end) || s.blocks[0]
    const m = MODES[cur.mode]
    if (family === "accessoryInline") {
      w.addText(`Küte ${st.text} · avg ${fmt(s.avg)}`)
    } else if (family === "accessoryCircular") {
      w.addText(st.text.split(" ").pop()).centerAlignText()
      w.addText(pad(cur.end % 24)).centerAlignText()
    } else {
      addText(w, `Küte praegu: ${st.text}`, Font.boldSystemFont(14), Color.white())
      addText(w, `${m.icon} ${m.label} until ${pad(cur.end % 24)}:00 · avg ${fmt(s.avg)}`, Font.systemFont(12), Color.white())
      const after = s.blocks[s.blocks.indexOf(cur) + 1]
      if (after) addText(w, `then ${MODES[after.mode].icon} ${MODES[after.mode].label}`, Font.systemFont(12), Color.white())
    }
    return w
  }

  w.backgroundColor = BG
  if (!s) {
    addText(w, "Küte täna", Font.boldSystemFont(15), TEXT)
    w.addSpacer(4)
    addText(w, error || "No plan for today yet.", Font.systemFont(12), DIM).lineLimit = 4
    return w
  }
  if (family === "medium") {
    w.setPadding(12, 14, 10, 14)
    const cols = w.addStack()
    cols.size = new Size(0, 82)
    const left = cols.addStack()
    left.layoutVertically()
    statusLines(left, st, 18)
    left.addSpacer(4)
    addText(left, `Avg ${fmt(s.avg)} s/kWh`, Font.semiboldSystemFont(12), TEXT)
    addText(left, `Peak ${pad(s.peak.h)}:00 · ${fmt(s.peak.price)}`, Font.semiboldSystemFont(12), MODES.HI.color)
    left.addSpacer()
    cols.addSpacer()
    const right = cols.addStack()
    right.layoutVertically()
    addBlocks(right, s.blocks, hour, 5, 12)
    right.addSpacer()
    w.addSpacer(6)
    const img = w.addImage(chart(s, hour, 300, 40))
    img.imageSize = new Size(300, 40)
    img.centerAlignImage()
  } else if (family === "large" || family === "extraLarge") {
    w.setPadding(16, 16, 16, 16)
    header(w, s, st, true)
    w.addSpacer(10)
    addBlocks(w, s.blocks, hour, 11, 15)
    w.addSpacer()
    const img = w.addImage(chart(s, hour, 300, 60))
    img.imageSize = new Size(300, 60)
    img.centerAlignImage()
  } else {
    w.setPadding(12, 12, 12, 12)
    statusLines(w, st, 15)
    w.addSpacer(3)
    addText(w, `Avg ${fmt(s.avg)} · Peak ${pad(s.peak.h)}`, Font.systemFont(11), DIM)
    w.addSpacer(5)
    addBlocks(w, s.blocks, hour, 3, 12)
    w.addSpacer()
  }
  return w
}

const now = new Date()
const data = await loadToday(now)
const s = data.error ? null : summarize(data.hours, data.valik, data.travel)
const st = currentStatus(data, s, tallinn(now).hour)
const error = data.error || (s ? null : "No plan for today yet.")

if (config.runsInWidget || config.runsInAccessoryWidget) {
  Script.setWidget(buildWidget(s, st, error, now, config.widgetFamily))
} else {
  Script.setShortcutOutput(s ? asText(s, st) : error)
  if (config.runsInApp) await buildWidget(s, st, error, now, "medium").presentMedium()
}
Script.complete()
