# Runs the generated Küte plaan in the simulator and compares it to proto.py on the same horizon.
# Usage: python3 -I tools/test_plan.py "2025-12-02 15:00" TMIN_TODAY TMIN_TOMORROW
import io, json, os, plistlib, sys, contextlib, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
import proto
from sim import Sim, TZ
from zoneinfo import ZoneInfo
# PHONE=America/New_York runs it with the phone in another time zone; the plan must not change
PHONE = ZoneInfo(os.environ.get('PHONE', 'Europe/Tallinn'))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
flows = {n: plistlib.load(open(os.path.join(ROOT, 'build', n + '.wflow'), 'rb'))
         for n in ('Kyte seaded', 'Küte plaan', 'S67 Küte (uus)', 'Kyte test run', 'Küte valik')}

now = dt.datetime.strptime(sys.argv[1], '%Y-%m-%d %H:%M').replace(tzinfo=TZ)
t1, t2 = float(sys.argv[2]), float(sys.argv[3])
tmr = now + dt.timedelta(days=1)
wx = {'daily': {'time': [str(now.date()), str(tmr.date())], 'temperature_2m_min': [t1, t2]}}
sim = Sim(flows, now, http={'https://api.open-meteo.com': wx}, phone=PHONE)
sim.run('Küte plaan')
plan = json.loads(sim.files['kyte-plan.json'])

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    st = now.replace(minute=0)
    end = dt.datetime(tmr.year, tmr.month, tmr.day, 23, 59, 59, tzinfo=TZ)
    proto.plan(st, end, {str(now.date()): t1, str(tmr.date()): t2})
ok = True
for line in buf.getvalue().splitlines():
    k, p, t, m, w = line.split(None, 4)
    v = plan.get(k[:11] + str(int(k[11:13])), '-|-|-|-')
    sm, sw, sp, sd = v.split('|')
    sm_cmp = 'ASK' if sm == 'ASK1' else sm
    flag = '' if sm_cmp == m else '   <-- MISMATCH'
    ok &= not flag
    print(k, p, t, f'{m:4} {sm:5}', sw, sp, sd, flag)
print('MATCH' if ok else 'DIFFERENCES', '| hours', len(plan) - 1, '| steps', sim.steps)
print('state:', sim.files.get('kyte-state.json'), '| made', plan['made'])
if os.environ.get('SAVE'):
    open(os.environ['SAVE'], 'w').write(sim.files['kyte-plan.json'])
