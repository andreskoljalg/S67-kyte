# Runs S67 Küte (uus) and Küte valik in the simulator against a plan made by Küte plaan.
# Usage: python3 -I tools/test_run.py
import json, os, plistlib, sys, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from sim import Sim, TZ

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
flows = {n: plistlib.load(open(os.path.join(ROOT, 'build', n + '.wflow'), 'rb'))
         for n in ('Kyte seaded', 'Küte plaan', 'S67 Küte (uus)', 'Kyte test run', 'Küte valik')}
quiet = lambda *a: None


def at(s):
    return dt.datetime.strptime(s, '%Y-%m-%d %H:%M').replace(tzinfo=TZ)


def make_plan(now, t1, t2):
    tmr = now + dt.timedelta(days=1)
    wx = {'daily': {'time': [str(now.date()), str(tmr.date())], 'temperature_2m_min': [t1, t2]}}
    sim = Sim(flows, now, http={'https://api.open-meteo.com': wx}, log=quiet)
    sim.run('Küte plaan')
    return sim.files, sim.reminders


def hour(now, files, reminders, label):
    notes = []
    sim = Sim(flows, now, files=dict(files), reminders=reminders,
              log=lambda *a: notes.append(' '.join(map(str, a))) if a[0] in ('NOTIFY', 'SCENE') else None)
    sim.run('S67 Küte (uus)')
    dry = Sim(flows, now, files=dict(files), reminders=[dict(r) for r in reminders], log=quiet)
    out = dry.run('Kyte test run')
    print(f'{label:34} ' + ' | '.join(notes) + f'   [test run: {out[0]}] steps {sim.steps}')
    return sim.scenes


files, rems = make_plan(at('2026-01-19 15:00'), -10, -12)
plan = json.loads(files['kyte-plan.json'])
print('reminders:', [r['title'] for r in rems])
mode = {k: v.split('|')[0] for k, v in plan.items() if k != 'made'}
asks = [k for k, m in mode.items() if m.startswith('ASK')]
plain = [k for k, m in mode.items() if m in ('ON', 'HI', 'OFF')]
print('ASK hours:', asks)


def key_time(k):
    return at(f'{k[:10]} {int(k[11:]):02d}:05')


k_plain = plain[0]
k_ask1 = next(k for k in asks if mode[k] == 'ASK1')
k_ask = next((k for k in asks if mode[k] == 'ASK' and k[:10] == k_ask1[:10]), k_ask1)
print('plan hit', k_plain, mode[k_plain], '| ASK1', k_ask1, '| ASK', k_ask)

hour(key_time(k_plain), files, [dict(r) for r in rems], f'plan {mode[k_plain]}')
for k in (k_ask1, k_ask):
    tag = mode[k]
    hour(key_time(k), files, [dict(r) for r in rems], f'{tag} reminder untouched')
    hour(key_time(k), files, [dict(r, done=True) for r in rems], f'{tag} reminder completed')
    hour(key_time(k), files, [], f'{tag} reminder deleted')
    for v in ('all', 'one', 'none', 'reset'):
        f = dict(files)
        d = k[:10]
        f['kyte-valik.json'] = json.dumps({d: v})
        hour(key_time(k), f, [], f'{tag} deleted + valik {v}')

# No plan file: live price fallback
hour(at('2026-01-19 18:05'), {}, [], 'no plan (live)')
hour(at('2026-01-20 03:05'), {}, [], 'no plan (live, quiet hours)')

# Küte valik: one / homme
for choice in (['Küta ainult 1 odavaim tund', 'Homme'], ['Küta kõik küsitud tunnid', 'Täna'], ['Ära küta', 'Täna'], ['Tühista valik (kasuta meeldetuletust)', 'Täna']):
    notes = []
    sim = Sim(flows, at('2026-01-19 16:00'), files={}, menu=list(choice),
              log=lambda *a: notes.append(' '.join(map(str, a))) if a[0] == 'NOTIFY' else None)
    try:
        sim.run('Küte valik')
        print('valik', choice, '->', sim.files.get('kyte-valik.json'), '|', *notes)
    except ValueError as e:
        print('valik', choice, 'menu titles differ:', e)

# The phone abroad: the same hour of the plan, the same scene, and the reminders' date prefix still matches
from zoneinfo import ZoneInfo
for zone in ('Europe/London', 'America/New_York', 'Asia/Kolkata'):
    for k in (k_plain, k_ask1):
        a = Sim(flows, key_time(k), files=dict(files), reminders=[dict(r, done=True) for r in rems], log=quiet)
        a.run('S67 Küte (uus)')
        b = Sim(flows, key_time(k), files=dict(files), reminders=[dict(r, done=True) for r in rems], log=quiet,
                phone=ZoneInfo(zone))
        b.run('S67 Küte (uus)')
        print(f'abroad {zone:17} {k:14}', 'SAME' if a.scenes == b.scenes else 'DIFF', b.scenes,
              b.files['kyte-praegu.json'])


def with_setting(key, value):
    f = dict(flows)
    wf = plistlib.loads(plistlib.dumps(flows['Kyte seaded']))
    A = wf['WFWorkflowActions']
    row = next(r for r in A[-2]['WFWorkflowActionParameters']['WFItems']['Value']['WFDictionaryFieldValueItems']
               if r['WFKey']['Value']['string'] == key)
    uuid = list(row['WFValue']['Value']['attachmentsByRange'].values())[0]['OutputUUID']
    act = next(a for a in A if a['WFWorkflowActionParameters'].get('UUID') == uuid)
    act['WFWorkflowActionParameters']['WFTextActionText'] = value
    f['Kyte seaded'] = wf
    return f


# Travel mode: no approval reminders; every hour OFF unless the price is below 3 s/kWh
tf = with_setting('travel_mode', 'true')
now = at('2026-10-22 15:00')
sim = Sim(tf, now, http={'https://api.open-meteo.com': {'daily': {'temperature_2m_min': [-10, -12]}}}, log=quiet)
sim.run('Küte plaan')
tplan = json.loads(sim.files['kyte-plan.json'])
print('travel: reminders', sim.reminders)
bad = []
for k, v in tplan.items():
    if k == 'made':
        continue
    price = float(v.split('|')[2])
    r = Sim(tf, key_time(k), files=dict(sim.files), log=quiet)
    r.run('S67 Küte (uus)')
    want = 'Küte-on' if price < 3 else 'Küte-off'
    if r.scenes != [want]:
        bad.append((k, price, r.scenes))
cheap = sorted(float(v.split('|')[2]) for k, v in tplan.items() if k != 'made' and float(v.split('|')[2]) < 3)
print('travel hours', len(tplan) - 1, '| below 3:', cheap, '| wrong:', bad or 'none')
print('travel status file', r.files['kyte-praegu.json'])
# a comma in the plan price, and no plan at all
f = dict(sim.files)
k = next(iter(x for x in tplan if x != 'made'))
f['kyte-plan.json'] = json.dumps({k: 'ON|tava|2,5|1'})
r = Sim(tf, key_time(k), files=f, log=quiet); r.run('S67 Küte (uus)')
print('travel, price "2,5":', r.scenes)
r = Sim(tf, at('2026-01-19 18:05'), files={}, log=quiet); r.run('S67 Küte (uus)')
print('travel, no plan:', r.scenes, r.files['kyte-praegu.json'])
