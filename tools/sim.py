# Executes generated workflow plists with approximate Shortcuts semantics, to test the logic off-device.
import json, math, plistlib, re, urllib.request, datetime as dt
from zoneinfo import ZoneInfo

OBJ = '￼'
TZ = ZoneInfo('Europe/Tallinn')


class Stop(Exception):
    pass


def fmt_num(x):
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    if isinstance(x, float):
        return ('%.10f' % x).rstrip('0').rstrip('.')
    return str(x)


# How a dictionary is turned into text; tests change it to mimic other key orders and layouts.
JSON_STYLE = {}


def to_str(v):
    if v is None:
        return ''
    if isinstance(v, (int, float)):
        return fmt_num(float(v))
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, **JSON_STYLE)
    if isinstance(v, list):
        return '\n'.join(to_str(x) for x in v)
    if isinstance(v, dt.datetime):
        return v.isoformat()
    return str(v)


def to_num(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if v is None or v == '':
        raise ValueError('number from nothing')
    return float(v)


def icu(d, pat):
    out, i = '', 0
    while i < len(pat):
        ch = pat[i]
        if ch == "'":
            j = pat.index("'", i + 1)
            out += pat[i + 1:j]
            i = j + 1
            continue
        j = i
        while j < len(pat) and pat[j] == ch:
            j += 1
        tokn = pat[i:j]
        rep = {'yyyy': '%Y', 'yy': '%y', 'MM': '%m', 'dd': '%d', 'HH': '%H', 'mm': '%M', 'ss': '%S', 'Z': '%z'}
        out += str(d.hour) if tokn == 'H' else d.strftime(rep[tokn]) if tokn in rep else tokn
        i = j
    return out


def strict_num(x, what):
    # What the device showed: decimal strings in number fields lose their decimals on comma locales,
    # and a repeat count given as text runs zero times.
    if isinstance(x, str) and not re.fullmatch(r'-?\d+', x):
        raise ValueError(f'{what}: non-integer literal {x!r}')


class Sim:
    def __init__(self, flows, now, files=None, reminders=None, menu=None, http=None, log=print, phone=TZ):
        # phone: the time zone the phone is set to; dates are shown and adjusted in it
        self.flows, self.now, self.phone = flows, now, phone
        self.files = files if files is not None else {}
        self.reminders = reminders if reminders is not None else []
        self.menu = list(menu or [])
        self.http = http or {}
        self.log = log
        self.scenes = []
        self.notes = []
        self.steps = 0
        self.hist = {}

    def run(self, name):
        A = self.flows[name]['WFWorkflowActions']
        groups = {}
        for i, a in enumerate(A):
            g = a['WFWorkflowActionParameters'].get('GroupingIdentifier')
            if g:
                groups.setdefault(g, []).append(i)
        out, var, frames = {}, {}, []
        last = [None]
        result = [None]

        def ref(r):
            t = r.get('Type')
            if t == 'ActionOutput':
                v = out.get(r['OutputUUID'])
            elif t == 'Variable':
                n = r['VariableName']
                if n == 'Repeat Index':
                    v = frames[-1]['idx']
                elif n == 'Repeat Item':
                    v = frames[-1]['item']
                else:
                    if n not in var:
                        raise KeyError('unset variable ' + n)
                    v = var[n]
            else:
                raise ValueError(r)
            for ag in r.get('Aggrandizements', []):
                if ag['Type'] == 'WFCoercionVariableAggrandizement':
                    v = to_str(v) if ag['CoercionItemClass'] == 'WFStringContentItem' else to_num(v)
            return v

        def val(x):
            if isinstance(x, (str, int, float, bool)):
                return x
            st = x.get('WFSerializationType')
            if st == 'WFTextTokenAttachment':
                return ref(x['Value'])
            if st == 'WFTextTokenString':
                s = x['Value']['string']
                rng = x['Value'].get('attachmentsByRange', {})
                if s == OBJ and rng:
                    return ref(list(rng.values())[0])
                parts = {int(re.match(r'\{(\d+)', k).group(1)): ref(v) for k, v in rng.items()}
                res, u16 = '', 0
                for ch in s:
                    if ch == OBJ and u16 in parts:
                        res += to_str(parts[u16])
                    else:
                        res += ch
                    u16 += len(ch.encode('utf-16-le')) // 2
                return res
            raise ValueError(x)

        def sval(x):
            return to_str(val(x))

        def cond(p):
            c = p['WFCondition']
            r0 = p['WFInput']['Variable']['Value']
            if c not in (0, 1, 2, 3, 100, 101) and not any(
                    ag.get('CoercionItemClass') == 'WFStringContentItem' for ag in r0.get('Aggrandizements', [])):
                raise ValueError('text condition without text coercion (crashes on the device)')
            v = ref(r0)
            if c in (0, 1, 2, 3):
                strict_num(p['WFNumberValue'], 'condition')
                a, b = to_num(v), to_num(val(p['WFNumberValue']))
                return [a < b, a <= b, a > b, a >= b][c]
            if c in (100, 101):
                has = v is not None and v != '' and v != []
                return has if c == 100 else not has
            a, b = to_str(v), sval(p['WFConditionalActionString'])
            return {4: a == b, 5: a != b, 8: a.startswith(b), 99: b in a}[c]

        pc = 0
        try:
            while pc < len(A):
                a = A[pc]
                ident = a['WFWorkflowActionIdentifier']
                p = a['WFWorkflowActionParameters']
                mode = p.get('WFControlFlowMode')
                g = p.get('GroupingIdentifier')
                if ident != 'is.workflow.actions.comment':
                    self.steps += 1
                    self.hist[pc] = self.hist.get(pc, 0) + 1
                r = None
                if ident == 'is.workflow.actions.conditional':
                    idx = groups[g]
                    if mode == 0:
                        if not cond(p):
                            pc = idx[1] + 1 if len(idx) == 3 else idx[-1] + 1
                            continue
                    elif mode == 1:
                        pc = idx[-1] + 1
                        continue
                    pc += 1
                    continue
                if ident in ('is.workflow.actions.repeat.count', 'is.workflow.actions.repeat.each'):
                    idx = groups[g]
                    if mode == 0:
                        if ident.endswith('count'):
                            if isinstance(p['WFRepeatCount'], str):
                                raise ValueError('repeat count as text runs zero times on the device')
                            its = [None] * int(to_num(val(p['WFRepeatCount'])))
                        else:
                            v = val(p['WFInput'])
                            its = v if isinstance(v, list) else ([] if v is None else [v])
                        if not its:
                            out[A[idx[-1]]['WFWorkflowActionParameters']['UUID']] = []
                            pc = idx[-1] + 1
                            continue
                        frames.append({'items': its, 'idx': 1, 'item': its[0], 'res': [], 'start': pc})
                        pc += 1
                        continue
                    f = frames[-1]
                    f['res'].append(last[0])
                    if f['idx'] < len(f['items']):
                        f['idx'] += 1
                        f['item'] = f['items'][f['idx'] - 1]
                        pc = f['start'] + 1
                        continue
                    frames.pop()
                    out[p['UUID']] = f['res']
                    pc += 1
                    continue
                if ident == 'is.workflow.actions.choosefrommenu':
                    idx = groups[g]
                    if mode == 0:
                        choice = self.menu.pop(0)
                        for k in idx[1:-1]:
                            if A[k]['WFWorkflowActionParameters']['WFMenuItemTitle'] == choice:
                                pc = k + 1
                                break
                        else:
                            raise ValueError('menu ' + choice)
                        continue
                    if mode == 1:
                        pc = idx[-1] + 1
                        continue
                    pc += 1
                    continue
                r = self.act(ident, p, val, sval, var, name)
                if ident == 'is.workflow.actions.output':
                    result[0] = r
                    raise Stop
                if 'UUID' in p:
                    out[p['UUID']] = r
                if ident != 'is.workflow.actions.comment':
                    last[0] = r
                pc += 1
        except Stop:
            pass
        except Exception:
            self.log('FAILED at action', pc, A[pc]['WFWorkflowActionIdentifier'],
                     {k: var.get(k) for k in ('i', 'H', 'n', 'step', 's0', 'L', 'loss', 'mm')})
            raise
        return result[0], var

    def act(self, ident, p, val, sval, var, flow):
        n = ident.rsplit('.', 1)[-1] if not ident.startswith('com.tuya') else 'tuya'
        if ident == 'is.workflow.actions.comment':
            return None
        if ident == 'is.workflow.actions.gettext':
            return sval(p['WFTextActionText'])
        if ident == 'is.workflow.actions.number':
            strict_num(p['WFNumberActionNumber'], 'number action')
            return float(p['WFNumberActionNumber'])
        if ident == 'is.workflow.actions.setvariable':
            var[p['WFVariableName']] = val(p['WFInput'])
            return var[p['WFVariableName']]
        if ident == 'is.workflow.actions.appendvariable':
            old = var.get(p['WFVariableName'])
            old = [] if old is None else (old if isinstance(old, list) else [old])
            var[p['WFVariableName']] = old + [val(p['WFInput'])]
            return var[p['WFVariableName']]
        if ident == 'is.workflow.actions.math':
            strict_num(p['WFMathOperand'], 'math operand')
            a, b = to_num(val(p['WFInput'])), to_num(val(p['WFMathOperand']))
            return {'+': lambda: a + b, '-': lambda: a - b, '×': lambda: a * b, '÷': lambda: a / b}[p['WFMathOperation']]()
        if ident == 'is.workflow.actions.round':
            x = to_num(val(p['WFInput']))
            if p.get('WFRoundMode') == 'Always Round Down':
                return float(math.floor(x))
            nd = {'Hundredths': 2, 'Ones Place': 0}[p['WFRoundTo']]
            return float(round(x + (1e-9 if x >= 0 else -1e-9), nd))
        if ident == 'is.workflow.actions.getvalueforkey':
            d = val(p['WFInput'])
            if isinstance(d, str):
                d = json.loads(d)
            if d is None:
                return None
            return d.get(sval(p['WFDictionaryKey']))
        if ident == 'is.workflow.actions.setvalueforkey':
            d = dict(val(p['WFDictionary']) or {})
            d[sval(p['WFDictionaryKey'])] = val(p['WFDictionaryValue'])
            return d
        if ident == 'is.workflow.actions.dictionary':
            d = {}
            for row in p['WFItems']['Value']['WFDictionaryFieldValueItems']:
                v = val(row['WFValue'])
                d[sval(row['WFKey'])] = to_num(v) if row['WFItemType'] == 3 else to_str(v)
            return d
        if ident == 'is.workflow.actions.detect.dictionary':
            v = val(p['WFInput'])
            return v if isinstance(v, dict) else json.loads(v)
        if ident == 'is.workflow.actions.getitemfromlist':
            lst = val(p['WFInput'])
            lst = lst if isinstance(lst, list) else [lst]
            if p['WFItemSpecifier'] == 'Item At Index':
                i = int(to_num(val(p['WFItemIndex'])))
                if not 1 <= i <= len(lst):
                    raise IndexError(f'item {i} of {len(lst)}')
                return lst[i - 1]
            a, b = int(to_num(val(p['WFItemRangeStart']))), int(to_num(val(p['WFItemRangeEnd'])))
            if not (1 <= a <= b <= len(lst)):
                raise IndexError(f'range {a}-{b} of {len(lst)}')
            return lst[a - 1:b]
        if ident == 'is.workflow.actions.count':
            v = val(p['Input'])
            return float(len(v) if isinstance(v, list) else (0 if v is None else 1))
        if ident == 'is.workflow.actions.statistics':
            v = val(p['Input'])
            v = v if isinstance(v, list) else [v]
            return sum(map(to_num, v)) / len(v)
        if ident == 'is.workflow.actions.text.replace':
            x, f, r = sval(p['WFInput']), p['WFReplaceTextFind'], p['WFReplaceTextReplace']
            r = r if isinstance(r, str) else sval(r)
            if p['WFReplaceTextRegularExpression']:
                return re.sub(f, re.sub(r'\$(\d)', r'\\\1', r), x)
            return x.replace(f, r)
        if ident == 'is.workflow.actions.text.match':
            return [m.group(0) for m in re.finditer(p['WFMatchTextPattern'], sval(p['text']))]
        if ident == 'is.workflow.actions.text.split':
            return sval(p['text']).split(p['WFTextCustomSeparator'])
        if ident == 'is.workflow.actions.date':
            return self.now.astimezone(self.phone)
        if ident == 'is.workflow.actions.format.date':
            return icu(val(p['WFDate']), p['WFDateFormat'])
        if ident == 'is.workflow.actions.adjustdate':
            d = val(p['WFDate'])
            q = p['WFDuration']['Value']
            if isinstance(q['Magnitude'], dict):
                raise ValueError('Adjust Date ignores a variable magnitude on the device')
            m = to_num(val(q['Magnitude']))
            unit = {'hr': 'hours', 'days': 'days', 'min': 'minutes'}[q['Unit']]
            d = d.astimezone(self.phone)
            if unit == 'days':
                return (d.replace(tzinfo=None) + dt.timedelta(days=m)).replace(tzinfo=self.phone)
            return (d.astimezone(dt.timezone.utc) + dt.timedelta(**{unit: m})).astimezone(self.phone)
        if ident == 'is.workflow.actions.converttimezone':
            # Tallinn → UTC moves the date by the offset difference; the result is shown in the phone's zone
            assert p['SourceTimeZone']['timeZone'] == 'Europe/Tallinn' and p['DestinationTimeZone']['timeZone'] == 'GMT'
            d = val(p['Date'])
            return (d - TZ.utcoffset(d.astimezone(TZ).replace(tzinfo=None))).astimezone(self.phone)
        if ident == 'is.workflow.actions.downloadurl':
            u = sval(p['WFURL'])
            for k, v in self.http.items():
                if u.startswith(k):
                    return v
            self.log('GET', u)
            return json.load(urllib.request.urlopen(u, timeout=30))
        if ident == 'is.workflow.actions.documentpicker.open':
            return self.files.get(p['WFGetFilePath'])
        if ident == 'is.workflow.actions.setitemname':
            return val(p['WFInput'])
        if ident == 'is.workflow.actions.documentpicker.save':
            self.files[p['WFFileDestinationPath']] = to_str(val(p['WFInput']))
            return p['WFFileDestinationPath']
        if ident == 'is.workflow.actions.notification':
            t = p['WFNotificationActionTitle']
            note = (t if isinstance(t, str) else sval(t), sval(p['WFNotificationActionBody']))
            self.notes.append(note)
            self.log('NOTIFY', *note)
            return None
        if ident == 'is.workflow.actions.exit':
            raise Stop
        if ident == 'is.workflow.actions.runworkflow':
            if not p['WFWorkflowName'].isascii():
                raise ValueError('Run Shortcut by an accented name may not find it')
            sub = Sim(self.flows, self.now, log=self.log, phone=self.phone)
            r, _ = sub.run(p['WFWorkflowName'])
            self.steps += sub.steps
            return r
        if ident == 'is.workflow.actions.output':
            return val(p['WFOutput'])
        if ident == 'is.workflow.actions.addnewreminder':
            rem = {'title': sval(p['WFCalendarItemTitle']), 'done': False}
            self.reminders.append(rem)
            self.log('REMINDER', rem['title'])
            return rem
        if ident == 'is.workflow.actions.setters.reminders':
            rem = val(p['WFInput'])
            rem['due'] = val(p['WFReminderContentItemDueDate'])
            return rem
        if ident == 'is.workflow.actions.filter.reminders':
            res = self.reminders
            for t in p['WFContentItemFilter']['Value']['WFActionParameterFilterTemplates']:
                if t['Property'] == 'Title':
                    pre = sval(t['Values']['String'])
                    res = [r for r in res if r['title'].startswith(pre)]
                else:
                    res = [r for r in res if r['done'] == t['Values']['Bool']]
            return res[:int(p['WFContentItemLimitNumber'])]
        if ident.startswith('com.tuya'):
            self.scenes.append(p['sceneData']['title']['key'])
            self.log('SCENE', p['sceneData']['title']['key'])
            return None
        raise NotImplementedError(ident)
