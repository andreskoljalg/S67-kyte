def load_settings(s, keys):
    s.setv('S', s.run(SETTINGS_NAME))
    for k in keys:
        s.setv(k, s.get(V('S'), k))


def inc(s, name, by=1):
    s.calc(name, V(name), '+', by)


def tz_off(s, name, d):
    """Tallinn's UTC offset in hours at date d: Convert Time Zone Tallinn → UTC moves the hour back by it,
    whatever time zone the phone is in. Anything but 2 or 3 is replaced by fallback."""
    s.setv(name, s.math(s.fmtd(d, 'H'), '-', s.fmtd(s.utc(d), 'H')))
    with s.IF(V(name), '<', 0):
        inc(s, name, 24)


def tallinn_now(s):
    """Sets rnow (the real time), toff (Tallinn UTC offset, 2 or 3) and now: a date whose clock, formatted on
    this phone, shows Tallinn time. All plan keys, hours and dates use now, so the plan is the same abroad."""
    s.comment('Tallinn time, wherever the phone is: shift the phone clock by (Tallinn offset - phone offset).')
    s.setv('rnow', s.now())
    tz_off(s, 'toff', V('rnow'))
    s.setv('tzok', 1)
    for op, v in (('<', 2), ('>', 3)):
        with s.IF(V('toff'), op, v):
            s.setv('tzok', 0)
            s.setv('toff', v)
    # the phone offset as "+0530": half hours = 2 × hours + minutes ÷ 30
    s.setv('zz', s.fmtd(V('rnow'), 'Z'))
    s.setv('zx', s.replace(V('zz'), '[+-]', ''))
    s.setv('zh', s.floor(s.math(V('zx', True), '÷', 100)))
    zm = s.math(V('zx', True), '-', s.math(V('zh'), '×', 100))
    s.setv('ph', s.math(s.math(V('zh'), '×', 2), '+', s.floor(s.math(zm, '÷', 30))))
    with s.IF(V('zz'), 'begins', '-'):
        s.setv('ph', s.math(0, '-', V('ph')))
    s.setv('sh', s.math(s.math(V('toff'), '×', 2), '-', V('ph')))
    with s.IF(V('tzok'), '<', 1):
        s.setv('sh', 0)
    s.setv('now', V('rnow'))
    # Adjust Date ignores a magnitude from a variable, so step 30 minutes at a time
    with s.IF(V('sh'), '>', 0):
        with s.REPEAT(V('sh')):
            s.setv('now', s.addd(V('now'), 30, 'min'))
    with s.IF(V('sh'), '<', 0):
        with s.REPEAT(s.math(0, '-', V('sh'))):
            s.setv('now', s.addd(V('now'), -30, 'min'))


def date_rates(s, n, date, ts1, off, summer):
    """Day-rate window for one date: sets ds{n}/de{n} (hours). ds = 99 when the whole day is night rate.
    summer is 1 in summer time, 0 in winter time."""
    s.setv(f'sum{n}', summer)
    # weekday, 0 = Monday: days since epoch (local) + 3, mod 7
    days = s.floor(s.math(s.math(ts1, '+', off), '÷', 86400))
    if n == 2:
        days = s.math(days, '+', 1)
    d3 = s.math(days, '+', 3)
    q = s.floor(s.math(d3, '÷', 7))
    s.setv(f'wd{n}', s.math(d3, '-', s.math(q, '×', 7)))
    s.calc(f'ds{n}', V(f'sum{n}'), '+', 7)
    s.calc(f'de{n}', V(f'sum{n}'), '+', 22)
    with s.IF(V(f'wd{n}'), '>', 4):
        s.setv(f'ds{n}', 99)
    with s.IF(V('holtxt'), 'contains', s.text(',', s.fmtd(date, 'MM-dd'), ',')):
        s.setv(f'ds{n}', 99)
    with s.IF(V('holtxt'), 'contains', s.text(',', s.fmtd(date, 'yyyy-MM-dd'), ',')):
        s.setv(f'ds{n}', 99)


def hour_key(s, idx):
    """Two-digit hour and plan key of hour number idx (1 = the hour the plan starts).
    Adjust Date ignores a magnitude from a variable on the device, so the main loop keeps both in lists."""
    return s.item(V('HL'), idx), s.item(V('K'), idx)


def set_slot(s, key, value, slot):
    """Replaces mode|why of an existing plan value, keeping price and day."""
    s.dset('PLAN', key, s.replace(value, SLOT, slot))


def process_block(s):
    """An expensive block (hours s0..e, day sd) has ended: preheat before it, comfort/approval hours inside it."""
    s.setv('bavg', s.avg(s.items(V('T'), V('s0'), V('e'))))
    s.setv('k', 0)
    # a peak shorter than preheat_min_block gets no preheating
    with s.IF(s.math(s.math(V('e'), '-', V('s0')), '+', 1), '>=', V('preheat_min_block')):
        with s.REPEAT(V('preheat_hours')):
            inc(s, 'k')
            s.calc('j', V('s0'), '-', V('k'))
            with s.IF(V('j'), '>=', 1):
                hj, kj = hour_key(s, V('j'))
                vj = s.get(V('PLAN'), kj)
                with s.IF(vj, 'begins', 'OFF') as b1:
                    b1.els()
                    with s.IF(vj, 'begins', 'ASK') as b2:
                        b2.els()
                        s.setv('qq', 0)
                        with s.IF(hj, '>=', V('quiet_start')):
                            with s.IF(hj, '<', V('quiet_end')):
                                s.setv('qq', 1)
                        with s.IF(s.item(V('P'), V('j')), '>', V('preheat_max_price')):
                            s.setv('qq', 1)
                        with s.IF(V('qq'), '<', 1):
                            gap = s.math(V('bavg'), '-', s.item(V('T'), V('j')))
                            with s.IF(gap, '>=', V('preheat_min_gap')):
                                set_slot(s, kj, vj, 'HI|eel')
    s.setv('tstart', V('t_on'))
    with s.IF(V('s0'), '>', 1):
        _, kp = hour_key(s, s.math(V('s0'), '-', 1))
        with s.IF(s.get(V('PLAN'), kp), 'begins', 'HI'):
            s.setv('tstart', V('t_hi'))
    s.setv('tout', V('tmin2'))
    with s.IF(V('sd'), '<', 2):
        s.setv('tout', V('tmin1'))
    # cooling in hundredths of a degree per hour, and how many hours the house stays above t_floor
    s.setv('lossc', s.math(s.math(s.math(V('t_on'), '-', V('tout')), '×', 100), '÷', V('loss_factor')))
    with s.IF(V('lossc'), '<', 5):
        s.setv('lossc', 5)
    for name, top in (('mm', 'tstart'), ('mon', 't_on')):
        s.setv(name, s.floor(s.math(s.math(s.math(V(top), '-', V('t_floor')), '×', 100), '÷', V('lossc'))))
        with s.IF(V(name), '<', 1):
            s.setv(name, 1)
    s.setv('pos', V('s0'))
    # while the rest of the block is longer than the house can hold, heat the cheapest hour in reach;
    # each pick moves pos forward, so e - s0 + 1 - mon passes are enough
    with s.REPEAT(s.math(s.math(V('e'), '-', V('s0')), '+', s.math(1, '-', V('mon')))):
        rest = s.math(s.math(V('e'), '-', V('pos')), '+', 1)
        with s.IF(rest, '>', V('mm')):
            s.setv('best', 99999)
            s.setv('c', V('pos'))
            s.setv('x', V('pos'))
            with s.REPEAT(s.math(V('mm'), '+', 1)):
                tx = s.item(V('T'), V('x'))
                with s.IF(tx, '<', V('best')):
                    s.setv('best', tx)
                    s.setv('c', V('x'))
                inc(s, 'x')
            hh, kc = hour_key(s, V('c'))
            s.setv('kc', kc)
            s.setv('vc', s.get(V('PLAN'), V('kc')))
            s.setv('nm', 'ON|mug')
            with s.IF(V('best'), '>', V('ask_above')):
                with s.IF(V('tout'), '>', V('ask_never_below')):
                    s.setv('nm', 'ASK|kys')
                    with s.IF(V('c'), '<', V('i2')) as br:
                        ask_add(s, 1, hh)
                        br.els()
                        ask_add(s, 2, hh)
            set_slot(s, V('kc'), V('vc'), V('nm'))
            s.calc('pos', V('c'), '+', 1)
            s.setv('mm', V('mon'))


def ask_add(s, d, hh):
    inc(s, f'na{d}')
    s.calc(f'as{d}', V(f'as{d}'), '+', V('best'))
    s.setv(f'hrs{d}', s.text(V(f'hrs{d}'), hh, ', '))
    with s.IF(V('best'), '<', V(f'b{d}')):
        s.setv(f'b{d}', V('best'))
        s.setv(f'ck{d}', V('kc'))


def ask_day(s, d, dd, dm):
    """Marks the cheapest approval hour of day d as ASK1 and creates the reminder once per date."""
    with s.IF(V(f'na{d}'), '>', 0):
        set_slot(s, V(f'ck{d}'), s.get(V('PLAN'), V(f'ck{d}')), 'ASK1|kys')
        with s.IF(s.get(V('ST'), dd), 'none'):
            dark = s.count(s.match(s.text(V('PLAN')), r'"(OFF|ASK1?)\|[^"]*\|%d"' % d))
            avgp = s.rnd(s.math(V(f'as{d}'), '÷', V(f'na{d}')))
            cost = s.rnd(s.math(s.math(V(f'as{d}'), '×', V('kwh_per_hour')), '÷', 100))
            hrs = s.replace(V(f'hrs{d}'), r',\s*$', '')
            title = s.text('Küte ', dm, ': ', dark, ' h väljas. Kas kütan ', V(f'na{d}'), ' h (', hrs,
                           ') à ', avgp, ' s/kWh ≈ ', cost, ' €? (tehtuks = jah, kustuta = ei)')
            r = s.add('is.workflow.actions.addnewreminder', {
                'WFCalendarItemTitle': tok(title),
                'WFCalendarItemNotes': 'Märgi tehtuks = kütan need tunnid. Kustuta = ei küta. '
                                       'Jäta puutumata = seadete ask_default. Rohkem valikuid: Küte valik.'},
                'New Reminder')
            due = s.addd(V('rnow'), 2, 'min')
            s.add('is.workflow.actions.setters.reminders', {
                'Mode': 'Set', 'WFContentItemPropertyName': 'Due Date', 'WFInput': att(r),
                'WFReminderContentItemDueDate': tok(due)}, 'Edited Reminder')
            s.dset('ST', dd, 'küsitud')


def build_plan():
    s = SC()
    s.comment('Küte plaan – run by an automation at 15:00.\n'
              'Fetches Elering prices from this hour to the end of tomorrow and the weather forecast, decides '
              'OFF / ON / HI / ASK for every hour and saves it to iCloud Drive/Shortcuts/' + PLAN_FILE + '.\n'
              'Creates an approval reminder for very expensive days.')
    load_settings(s, ['off_above', 'hi_below', 'vat', 'net_day', 'net_night', 'holidays', 'quiet_start',
                      'quiet_end', 'preheat_hours', 'preheat_min_gap', 'preheat_min_block', 'preheat_max_price',
                      'delay_min_gap', 't_on', 't_hi', 't_floor',
                      'loss_factor', 'ask_above', 'ask_never_below', 'kwh_per_hour', 'lat', 'lon',
                      'plan_notification', 'travel_mode'])
    # added later: an older Kyte seaded without them still works
    for k, v in (('preheat_min_block', 2), ('preheat_max_price', 12)):
        with s.IF(V(k), 'none'):
            s.setv(k, v)
    tallinn_now(s)
    s.setv('base', s.addd(V('now'), -1, 'hr'))
    s.setv('tmr', s.addd(V('now'), 1, 'days'))
    s.setv('today', s.fmtd(V('now'), 'yyyy-MM-dd'))
    s.setv('tomorrow', s.fmtd(V('tmr'), 'yyyy-MM-dd'))
    s.setv('holtxt', s.text(',', V('holidays'), ','))

    s.comment('Prices from the start of this hour to the end of tomorrow (Tallinn time). A text replace turns '
              'every {"timestamp":…,"price":…} into its price, so no loop is needed to read them.')
    start = s.fmtd(s.utc(V('now')), "yyyy-MM-dd'T'HH'%3A'00'%3A'00.000'Z'")
    # Tallinn offset at this time tomorrow; the end of tomorrow is 21:59 UTC in winter, 20:59 in summer
    tz_off(s, 'toff2', s.addd(V('rnow'), 1, 'days'))
    for op, v in (('<', 2), ('>', 3)):
        with s.IF(V('toff2'), op, v):
            s.setv('toff2', V('toff'))
    s.setv('eh', s.math(23, '-', V('toff2')))
    body = s.url('https://dashboard.elering.ee/api/nps/price?start=', start, '&end=', V('tomorrow'), 'T', V('eh'),
                 '%3A59%3A00.000Z')
    s.setv('ts', s.match(body, TS_RX))
    prices = s.replace(body, PRICE_RX, '$1')
    s.setv('PR', s.get(s.get(s.todict(prices), 'data'), 'ee'))
    s.setv('n', s.count(V('PR')))
    with s.IF(V('n'), '<', 2):
        s.notify('Küte plaan ⚠️', 'Elering ei andnud hindu, plaani ei tehtud.')
        s.exit()
    s.setv('ts1', s.item(V('ts'), 1))
    s.setv('step', s.rnd(s.math(3600, '÷', s.math(s.item(V('ts'), 2), '-', V('ts1'))), 'Ones Place'))
    s.setv('sm1', s.math(V('step'), '-', 1))
    s.setv('H', s.floor(s.math(V('n'), '÷', V('step'))))
    with s.IF(V('H'), '<', 1):
        s.notify('Küte plaan ⚠️', 'Elering andis hinnad, aga neist ei saanud tunde lugeda. Plaani ei tehtud.')
        s.exit()
    s.setv('mult', s.math(s.math(V('vat'), '+', 100), '÷', 1000))

    s.comment('Network fee day-rate hours for today (1) and tomorrow (2). Weekends and holidays are night rate.')
    s.setv('off1', s.math(V('toff'), '×', 3600))
    date_rates(s, 1, V('now'), V('ts1'), V('off1'), s.math(V('toff'), '-', 2))
    date_rates(s, 2, V('tmr'), V('ts1'), V('off1'), s.math(V('toff2'), '-', 2))

    s.comment('Weather: minimum temperature today and tomorrow (Open-Meteo).')
    wx = s.url('https://api.open-meteo.com/v1/forecast?latitude=', V('lat'), '&longitude=', V('lon'),
               '&daily=temperature_2m_min&timezone=Europe%2FTallinn&forecast_days=2')
    tl = s.get(s.get(wx, 'daily'), 'temperature_2m_min')
    s.setv('tmin1', s.item(tl, 1))
    s.setv('tmin2', s.item(tl, 2))

    s.setv('PLAN', s.dictionary([('made', s.fmtd(V('now'), 'yyyy-MM-dd HH:mm'), 0)]))
    for name, v in (('ds', V('ds1')), ('de', V('de1')), ('dd', 1), ('i2', 999), ('pt', 0), ('inb', 0), ('fin', 0),
                    ('pm1', '-'), ('pm2', '-')):
        s.setv(name, v)
    for d in (1, 2):
        for name, v in (('na', 0), ('as', 0), ('hrs', '-'), ('b', 99999), ('ck', '-')):
            s.setv(f'{name}{d}', v)
        s.setv(f'hrs{d}', s.text(''))

    s.comment('One pass over the hours. Each hour gets "MODE|reason|price|day" in PLAN. The previous hour is '
              'checked for waiting, and an expensive block is handled as soon as it ends.')
    # Repeat Index read back empty on the device, so the hour number is counted by hand.
    s.setv('i', 0)
    s.setv('dh', V('base'))
    with s.REPEAT(V('H')):
        s.calc('i', V('i'), '+', 1)
        b = s.math(V('i'), '×', V('step'))
        p = s.rnd(s.math(s.avg(s.items(V('PR'), s.math(b, '-', V('sm1')), b)), '×', V('mult')))
        s.setv('dh', s.addd(V('dh'), 1, 'hr'))
        key = s.fmtd(V('dh'), KEY)
        hr = s.fmtd(V('dh'), 'HH')
        s.append('K', key)
        s.append('HL', hr)
        with s.IF(hr, '<', 1):
            with s.IF(V('i'), '>', 1):
                s.setv('ds', V('ds2'))
                s.setv('de', V('de2'))
                s.setv('dd', 2)
                s.setv('i2', V('i'))
        s.setv('fee', V('net_night'))
        with s.IF(hr, '>=', V('ds')):
            with s.IF(hr, '<', V('de')):
                s.setv('fee', V('net_day'))
        t = s.math(p, '+', V('fee'))
        s.append('T', t)
        s.append('P', p)
        s.setv('mw', 'ON|tava')
        with s.IF(p, '<', V('hi_below')):
            s.setv('mw', 'HI|odav')
            with s.IF(hr, '>=', V('quiet_start')):
                with s.IF(hr, '<', V('quiet_end')):
                    s.setv('mw', 'ON|oo')
        with s.IF(p, '>', V('off_above')):
            s.setv('mw', 'OFF|tipp')
        s.dset('PLAN', key, s.text(V('mw'), '|', p, '|', V('dd')))
        # wait: the previous ON hour is skipped when this hour is much cheaper
        with s.IF(s.math(V('pt'), '-', t), '>=', V('delay_min_gap')):
            with s.IF(V('pm1'), 'begins', 'ON|'):
                with s.IF(V('mw'), 'begins', 'OFF') as br:
                    br.els()
                    with s.IF(V('pm2'), 'begins', 'OFF') as br2:
                        br2.els()
                        _, kp = hour_key(s, s.math(V('i'), '-', 1))
                        set_slot(s, kp, s.get(V('PLAN'), kp), 'OFF|ootan')
                        s.setv('pm1', 'OFF')
        with s.IF(V('mw'), 'begins', 'OFF') as br:
            with s.IF(V('inb'), '<', 1):
                s.setv('s0', V('i'))
                s.setv('sd', V('dd'))
                s.setv('inb', 1)
            with s.IF(V('i'), '>=', V('H')):
                s.setv('e', V('i'))
                s.setv('fin', 1)
            br.els()
            with s.IF(V('inb'), '>', 0):
                s.setv('e', s.math(V('i'), '-', 1))
                s.setv('fin', 1)
        # one copy of the block logic, for a block that ended here or runs to the end of the plan
        with s.IF(V('fin'), '>', 0):
            process_block(s)
            s.setv('inb', 0)
            s.setv('fin', 0)
        s.setv('pm2', V('pm1'))
        s.setv('pm1', V('mw'))
        s.setv('pt', t)

    s.comment('Approval: mark the cheapest asked hour per day (ASK1) and create the reminder once per date.')
    s.setv('ST', s.emptydict())
    f = s.getfile(STATE_FILE)
    with s.IF(f, 'has'):
        s.setv('ST', s.todict(f))
    # travel mode heats only very cheap hours, so there is nothing to approve
    with s.IF(V('travel_mode'), 'is', 'true') as br:
        br.els()
        ask_day(s, 1, V('today'), s.fmtd(V('now'), 'dd.MM.yy'))
        ask_day(s, 2, V('tomorrow'), s.fmtd(V('tmr'), 'dd.MM.yy'))
    s.savefile(s.text(V('ST')), STATE_FILE)
    s.setv('js', s.text(V('PLAN')))
    s.savefile(V('js'), PLAN_FILE)
    with s.IF(V('plan_notification'), 'is', 'true'):
        heat = s.count(s.match(V('js'), r'"(ON|HI)\|[^"]*\|2"'))
        dark = s.count(s.match(V('js'), r'"OFF\|[^"]*\|2"'))
        with s.IF(s.math(heat, '+', dark), '>', 0):
            s.notify('Küte homme', heat, ' h kütet, ', dark, ' h väljas, ', V('na2'), ' h ootab kinnitust')
    s.output(V('js'))
    return workflow(s)


def build_run(dry=False):
    s = SC()
    if dry:
        s.comment('Kyte test run – the same decision as S67 Küte (uus) but it never switches the heating. '
                  'It outputs mode | reason | price. Safe to run any time; delete it when you no longer need it.')
    else:
        s.comment('S67 Küte – run every hour by an automation.\n'
                  'Reads this hour from the plan made by Küte plaan and switches the Tuya scene. Without a plan it '
                  'decides from the current price, like the old version.')
    load_settings(s, ['enabled', 'notifications', 'off_above', 'hi_below', 'vat', 'quiet_start', 'quiet_end',
                      'ask_default', 'travel_mode', 'travel_on_below'])
    with s.IF(V('travel_on_below'), 'none'):
        s.setv('travel_on_below', 3)
    if not dry:
        with s.IF(V('enabled'), 'is not', 'true'):
            s.exit()
    tallinn_now(s)
    s.setv('v', s.text(''))
    f = s.getfile(PLAN_FILE)
    with s.IF(f, 'has'):
        s.setv('v', s.get(s.todict(f), s.fmtd(V('now'), KEY)))
    # an empty Text still counts as having a value, so look for the separator instead
    with s.IF(V('v'), 'contains', '|') as br:
        parts = s.split(V('v'), '|')
        s.setv('mode', s.item(parts, 1))
        s.setv('why', s.item(parts, 2))
        s.setv('price', s.item(parts, 3))
        br.els()
        s.comment('No plan for this hour: decide from the current price.')
        s.setv('mode', 'ON')
        s.setv('why', 'otse')
        s.setv('price', '?')
        u = s.utc(V('now'))
        body = s.url('https://dashboard.elering.ee/api/nps/price?start=',
                     s.fmtd(u, "yyyy-MM-dd'T'HH'%3A'00'%3A'00.000'Z'"), '&end=',
                     s.fmtd(u, "yyyy-MM-dd'T'HH'%3A'59'%3A'59.999'Z'"))
        lst = s.get(s.get(s.todict(s.replace(body, PRICE_RX, '$1')), 'data'), 'ee')
        with s.IF(s.count(lst), '>', 0):
            s.setv('price', s.rnd(s.math(s.avg(lst), '×', s.math(s.math(V('vat'), '+', 100), '÷', 1000))))
            with s.IF(V('price'), '<', V('hi_below')):
                s.setv('mode', 'HI')
                hr = s.fmtd(V('now'), 'H')
                with s.IF(hr, '>=', V('quiet_start')):
                    with s.IF(hr, '<', V('quiet_end')):
                        s.setv('mode', 'ON')
            with s.IF(V('price'), '>', V('off_above')):
                s.setv('mode', 'OFF')
    s.setv('why', s.get(s.dictionary([(k, t, 0) for k, t in WHY.items()]), V('why')))

    s.comment('Approval hours: Küte valik choice first, then the reminder (completed = yes, deleted = no, '
              'untouched = ask_default).')
    with s.IF(V('mode'), 'begins', 'ASK'):
        s.setv('ch', 'default')
        prefix = tok('Küte ', s.fmtd(V('now'), 'dd.MM.yy'))
        title_rule = {'Operator': 8, 'Property': 'Title', 'Removable': True, 'Values': {'String': prefix}}
        done_rule = {'Operator': 4, 'Property': 'Is Completed', 'Removable': True, 'Values': {'Bool': True}}

        def find(rules):
            return s.add('is.workflow.actions.filter.reminders', {
                'WFContentItemFilter': {'Value': {'WFActionParameterFilterPrefix': 1,
                                                  'WFActionParameterFilterTemplates': rules,
                                                  'WFContentPredicateBoundedDate': False},
                                        'WFSerializationType': 'WFContentPredicateTableTemplate'},
                'WFContentItemLimitEnabled': True, 'WFContentItemLimitNumber': 1.0}, 'Reminders')
        with s.IF(s.count(find([title_rule])), '>', 0) as br:
            with s.IF(s.count(find([title_rule, done_rule])), '>', 0):
                s.setv('ch', 'all')
            br.els()
            s.setv('ch', 'none')
        vf = s.getfile(VALIK_FILE)
        with s.IF(vf, 'has'):
            s.setv('vc', s.get(s.todict(vf), s.fmtd(V('now'), 'yyyy-MM-dd')))
            with s.IF(V('vc'), 'has'):
                with s.IF(V('vc'), 'is not', 'reset'):
                    s.setv('ch', V('vc'))
        s.setv('nm', 'OFF')
        with s.IF(V('ch'), 'is', 'default'):
            with s.IF(V('ask_default'), 'is', 'ON'):
                s.setv('nm', 'ON')
        with s.IF(V('ch'), 'is', 'all'):
            s.setv('nm', 'ON')
        with s.IF(V('ch'), 'is', 'one'):
            with s.IF(V('mode'), 'is', 'ASK1'):
                s.setv('nm', 'ON')
        s.setv('why', s.text(V('why'), ' → ', V('ch')))
        s.setv('mode', V('nm'))

    s.comment('Travel mode: OFF unless the price is below travel_on_below. Plan prices may be written with a dot '
              'or a comma, so they get this phone\'s decimal separator before the comparison.')
    with s.IF(V('travel_mode'), 'is', 'true'):
        s.setv('mode', 'OFF')
        sep = s.replace(s.text(s.math(1, '÷', 2)), '[0-9]', '')
        s.setv('pn', s.replace(V('price'), '[.,]', sep))
        with s.IF(V('price'), 'is not', '?'):
            with s.IF(V('pn'), '<', V('travel_on_below')):
                s.setv('mode', 'ON')
        s.setv('why', WHY['reis'])

    if dry:
        s.output(s.text(V('mode'), ' | ', V('why'), ' | ', V('price'), ' | Tallinn ', s.fmtd(V('now'), 'HH:mm')))
        return workflow(s, types=('WFWorkflowTypeShowInSearch',))

    s.comment('Switch the heating.')
    scene_idx = {}
    with s.IF(V('mode'), 'is', 'OFF') as br:
        s.comment('Heating OFF')
        s.add('com.tuya.smart.ThingSceneWidgetActionIntent', tuya('Küte-off'), 'Run Scene')
        scene_idx['Küte-off'] = len(s.A) - 1
        with s.IF(V('notifications'), 'is', 'true'):
            s.notify('Küte on väljas ❌', V('why'), ' · ', V('price'), ' s/kWh')
        br.els()
        with s.IF(V('mode'), 'is', 'HI') as br2:
            s.comment('Heating HI')
            s.add('com.tuya.smart.ThingSceneWidgetActionIntent', tuya('Küte-on-HI'), 'Run Scene')
            scene_idx['Küte-on-HI'] = len(s.A) - 1
            with s.IF(V('notifications'), 'is', 'true'):
                s.notify('Küte huugab 🔥', V('why'), ' · ', V('price'), ' s/kWh')
            br2.els()
            s.comment('Heating ON')
            s.add('com.tuya.smart.ThingSceneWidgetActionIntent', tuya('Küte-on'), 'Run Scene')
            scene_idx['Küte-on'] = len(s.A) - 1
            with s.IF(V('notifications'), 'is', 'true'):
                s.notify('Küte on sees ✅', V('why'), ' · ', V('price'), ' s/kWh')
    s.comment('Remember what was done this hour, for the Küte täna widget.')
    s.savefile(s.text(s.dictionary([(k, r, 0) for k, r in (
        ('t', s.fmtd(V('now'), KEY)), ('mode', V('mode')), ('why', V('why')), ('price', V('price')),
        ('travel', V('travel_mode')), ('tb', V('travel_on_below')))])), NOW_FILE)
    qtext = {'Küte-off': 'Sinu küte OFF action', 'Küte-on': 'Sinu küte ON action',
             'Küte-on-HI': 'Sinu "Küte-on-HI" scene'}
    questions = [{'ParameterKey': 'sceneData', 'Category': 'Parameter', 'ActionIndex': idx, 'Text': qtext[n],
                  'DefaultValue': s.A[idx]['WFWorkflowActionParameters']['sceneData']}
                 for n, idx in scene_idx.items()]
    return workflow(s, questions, types=('Watch', 'WFWorkflowTypeShowInSearch'))


