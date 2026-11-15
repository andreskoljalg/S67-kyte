# Generates the four Küte shortcuts as unsigned workflow plists in build/.
# Logic mirrors tools/proto.py.
import os, plistlib, sys
sys.path.insert(0, os.path.dirname(__file__))
from sc import SC, V, tok, att, workflow, write

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = plistlib.load(open(os.path.join(ROOT, 'build/orig/Shortcut.wflow'), 'rb'))
SETTINGS_NAME = 'Kyte seaded'  # ASCII: Run Shortcut may not find an accented name
PLAN_FILE, STATE_FILE, VALIK_FILE = 'kyte-plan.json', 'kyte-state.json', 'kyte-valik.json'
NOW_FILE = 'kyte-praegu.json'  # what the hourly shortcut last did, for the widget

# The plan stores a short reason code per hour; the hourly shortcut shows the text.
WHY = dict(tipp='kallis tund', tava='tavaline hind', oo='odav öö, ei kuumuta üle', odav='väga odav',
           ootan='järgmine tund on palju odavam', eel='eelküte enne kallist perioodi',
           mug='hoian miinimumtemperatuuri', kys='kallis, vajab kinnitust', otse='otse hinnast (plaani pole)',
           reis='reisirežiim')
KEY = "yyyy-MM-dd'T'H"
# A downloaded dictionary turned into text has no fixed key order, so neither pattern relies on it.
PRICE_RX = r'\{[^{}]*"price"\s*:\s*(-?[0-9.]+(?:[eE][-+]?\d+)?)[^{}]*\}'
TS_RX = r'(?<![\d.])\d{9,}(?![\d.])'
SLOT = r'^[^|]*\|[^|]*'  # mode|why at the start of a plan value


def tuya(name):
    for a in ORIG['WFWorkflowActions']:
        p = a['WFWorkflowActionParameters']
        if a['WFWorkflowActionIdentifier'].startswith('com.tuya') and p['sceneData']['title']['key'] == name:
            return {k: v for k, v in p.items() if k != 'UUID'}
    raise KeyError(name)


SETTINGS = [
    ('enabled', 0, 'true', 'Master switch. "true" = the hourly shortcut controls the heating, "false" = it does nothing.'),
    ('notifications', 0, 'true', 'Notification every hour saying what the heating does and why. "true" / "false".'),
    ('travel_mode', 0, 'false', 'Travel mode. "true" = heating is OFF except when the spot price incl. VAT is below '
                                'travel_on_below, and no approval reminders are made. "false" = normal.'),
    ('travel_on_below', 3, 3, 'In travel mode the heating is ON only when the spot price incl. VAT is below this '
                              '(s/kWh).'),
    ('plan_notification', 0, 'true', "Notification at 15:00 with tomorrow's plan. \"true\" / \"false\"."),
    ('off_above', 3, 15, 'Heating OFF when the hour\'s spot price incl. VAT is above this (s/kWh).'),
    ('hi_below', 3, 5, 'Heating HI when the spot price incl. VAT is below this (s/kWh). In quiet hours it is ON instead.'),
    ('vat', 3, 24, 'VAT in percent.'),
    ('net_day', 3, 4.58, 'Network fee, day rate (s/kWh). Weekdays 07-22 (08-23 in summer time).'),
    ('net_night', 3, 2.60, 'Network fee, night and weekend rate (s/kWh).'),
    ('holidays', 0, '01-01,02-24,05-01,06-23,06-24,08-20,12-24,12-25,12-26,2026-04-03,2027-03-26,2028-04-14',
     'Public holidays billed at the night rate. MM-dd repeats every year, yyyy-MM-dd for moving holidays '
     '(Good Friday). Comma separated, no spaces.'),
    ('quiet_start', 3, 0, 'Quiet hours start (hour). In quiet hours a cheap price gives ON instead of HI, '
                            'so the house does not get hot during the night.'),
    ('quiet_end', 3, 6, 'Quiet hours end (this hour is no longer quiet). Preheating can start from here.'),
    ('preheat_hours', 3, 2, 'How many hours before an expensive block can be preheated with HI.'),
    ('preheat_min_gap', 3, 7, 'Preheat only if that hour is at least this much cheaper than the expensive '
                                'block average (s/kWh incl. network fee).'),
    ('preheat_min_block', 3, 2, 'Preheat only before an expensive block of at least this many hours. '
                                  'A shorter peak is simply OFF.'),
    ('preheat_max_price', 3, 12, 'Preheat only in an hour whose own spot price incl. VAT is at most this (s/kWh).'),
    ('delay_min_gap', 3, 8, 'Skip an ON hour when the next hour is at least this much cheaper (s/kWh).'),
    ('t_on', 3, 22, 'Küte-on setpoint in °C.'),
    ('t_hi', 3, 24, 'Küte-on-HI setpoint in °C.'),
    ('t_floor', 3, 19, 'Lowest indoor temperature you accept during long expensive periods (°C).'),
    ('loss_factor', 3, 32, 'Heat loss of the house: °C lost per hour = (indoor - outdoor) / loss_factor. '
                             '32 means about 1 °C per hour at -10 °C. Smaller number = house cools faster.'),
    ('ask_above', 3, 25, 'A comfort hour costing more than this (s/kWh incl. network fee) needs your approval.'),
    ('ask_default', 0, 'OFF', 'What approval hours do when you leave the reminder unanswered: "ON" or "OFF".'),
    ('ask_never_below', 3, -15, 'At or below this night minimum outdoor temperature (°C) comfort hours run '
                                  'without asking.'),
    ('kwh_per_hour', 3, 5, 'Average consumption of one heating hour (kWh), used for cost estimates.'),
    ('lat', 0, '59.437', 'Your location for the weather forecast: latitude, with a dot.'),
    ('lon', 0, '24.754', 'Longitude, with a dot.'),
]


def build_settings():
    s = SC()
    s.comment('Küte seaded – all settings for Küte plaan, S67 Küte and Küte valik.\n'
              'Change the values below. Text values are in Text actions, numbers in Number actions.\n'
              'Numbers are stored so that every phone reads them the same; tap a number to change it.')
    rows, questions = [], []
    for key, typ, val, desc in SETTINGS:
        s.comment(f'{key}: {desc}')
        r = s.text(val) if typ == 0 else s.num(val)
        if key in ('lat', 'lon'):
            questions.append({'ParameterKey': 'WFTextActionText', 'Category': 'Parameter',
                              'ActionIndex': len(s.A) - 1, 'DefaultValue': val,
                              'Text': 'Sinu asukoht ilmaennustuse jaoks: ' +
                                      ('laiuskraad (latitude), punktiga' if key == 'lat' else
                                       'pikkuskraad (longitude), punktiga')})
        rows.append((key, r, typ))
    d = s.dictionary(rows)
    s.output(d)
    return workflow(s, questions, types=(), out_classes=('WFDictionaryContentItem',))




