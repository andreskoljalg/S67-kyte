# Small DSL for writing Apple Shortcuts workflow plists from Python.
import plistlib, uuid as _uuid
from contextlib import contextmanager

OBJ = '￼'
NUM_OPS = {'<': 0, '<=': 1, '>': 2, '>=': 3}
TXT_OPS = {'is': 4, 'is not': 5, 'begins': 8, 'contains': 99}
ANY_OPS = {'has': 100, 'none': 101}
C = 'is.workflow.actions.conditional'


def uid():
    return str(_uuid.uuid4()).upper()


TXT = [{'Type': 'WFCoercionVariableAggrandizement', 'CoercionItemClass': 'WFStringContentItem'}]
NUM = [{'Type': 'WFCoercionVariableAggrandizement', 'CoercionItemClass': 'WFNumberContentItem'}]
INPUT = {'Type': 'ExtensionInput'}


def V(name, num=False):
    r = {'Type': 'Variable', 'VariableName': name}
    if num:
        r['Aggrandizements'] = [{'Type': 'WFCoercionVariableAggrandizement',
                                 'CoercionItemClass': 'WFNumberContentItem'}]
    return r


def as_num(r):
    return dict(r, Aggrandizements=NUM)


def as_txt(r):
    return dict(r, Aggrandizements=TXT)


def att(r):
    return {'Value': r, 'WFSerializationType': 'WFTextTokenAttachment'}


def is_lit(x):
    return isinstance(x, (str, int, float))


def tok(*parts):
    s, rng = '', {}
    for p in parts:
        if is_lit(p):
            s += str(p)
        else:
            pos = len(s.encode('utf-16-le')) // 2
            rng['{%d, 1}' % pos] = p
            s += OBJ
    v = {'string': s}
    if rng:
        v['attachmentsByRange'] = rng
    return {'Value': v, 'WFSerializationType': 'WFTextTokenString'}


def operand(x):
    # Number fields: integers as strings work on every locale, decimal strings do not (4.58 reads as 0 with a
    # comma decimal separator), so decimals are refused here.
    if isinstance(x, float):
        if not x.is_integer():
            raise ValueError(f'decimal literal {x}: rewrite with integers')
        x = int(x)
    return str(x) if is_lit(x) else att(x)


class Branch:
    def __init__(self, sc, g):
        self.sc, self.g = sc, g

    def els(self):
        self.sc.add(C, {'GroupingIdentifier': self.g, 'WFControlFlowMode': 1})


class SC:
    def __init__(self):
        self.A = []

    def add(self, ident, params, out=None):
        p = dict(params)
        if out:
            p['UUID'] = uid()
        self.A.append({'WFWorkflowActionIdentifier': ident, 'WFWorkflowActionParameters': p})
        if out:
            return {'OutputName': out, 'OutputUUID': p['UUID'], 'Type': 'ActionOutput'}

    # values
    def comment(self, t):
        self.add('is.workflow.actions.comment', {'WFCommentActionText': t})

    def text(self, *parts):
        val = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else tok(*parts)
        return self.add('is.workflow.actions.gettext', {'WFTextActionText': val}, 'Text')

    def num(self, v):
        # stored as a plist number, which every locale reads correctly
        v = float(v) if isinstance(v, str) else v
        v = int(v) if float(v).is_integer() else float(v)
        return self.add('is.workflow.actions.number', {'WFNumberActionNumber': v}, 'Number')

    def lit(self, x):
        return x if not is_lit(x) else (self.text(x) if isinstance(x, str) else self.num(x))

    def setv(self, name, val):
        self.add('is.workflow.actions.setvariable',
                 {'WFInput': att(self.lit(val)), 'WFVariableName': name})

    def math(self, a, op, b):
        return self.add('is.workflow.actions.math', {'WFInput': att(self.lit(a)), 'WFMathOperation': op,
                                                     'WFMathOperand': operand(b)}, 'Calculation Result')

    def calc(self, name, a, op, b):
        self.setv(name, self.math(a, op, b))

    def rnd(self, a, to='Hundredths', mode=None):
        p = {'WFInput': att(a), 'WFRoundTo': to}
        if mode:
            p['WFRoundMode'] = mode
        return self.add('is.workflow.actions.round', p, 'Rounded Number')

    def floor(self, a):
        return self.rnd(a, 'Ones Place', 'Always Round Down')

    # dictionaries / lists
    def get(self, d, key):
        k = key if isinstance(key, str) else tok(key)
        return self.add('is.workflow.actions.getvalueforkey',
                        {'WFInput': att(d), 'WFDictionaryKey': k}, 'Dictionary Value')

    def dset(self, var, key, val):
        out = self.add('is.workflow.actions.setvalueforkey',
                       {'WFDictionary': att(V(var)), 'WFDictionaryKey': tok(key),
                        'WFDictionaryValue': tok(val)}, 'Dictionary')
        self.setv(var, out)

    def emptydict(self):
        return self.add('is.workflow.actions.dictionary',
                        {'WFItems': {'Value': {'WFDictionaryFieldValueItems': []},
                                     'WFSerializationType': 'WFDictionaryFieldValue'}}, 'Dictionary')

    def dictionary(self, items):
        # items: [(key, ref, itemtype)] itemtype 0 text, 3 number
        rows = [{'WFItemType': t, 'WFKey': tok(k), 'WFValue': tok(r)} for k, r, t in items]
        return self.add('is.workflow.actions.dictionary',
                        {'WFItems': {'Value': {'WFDictionaryFieldValueItems': rows},
                                     'WFSerializationType': 'WFDictionaryFieldValue'}}, 'Dictionary')

    def todict(self, x):
        return self.add('is.workflow.actions.detect.dictionary', {'WFInput': att(x)}, 'Dictionary')

    def item(self, lst, idx):
        return self.add('is.workflow.actions.getitemfromlist',
                        {'WFInput': att(lst), 'WFItemSpecifier': 'Item At Index',
                         'WFItemIndex': operand(idx)}, 'Item from List')

    def items(self, lst, a, b):
        return self.add('is.workflow.actions.getitemfromlist',
                        {'WFInput': att(lst), 'WFItemSpecifier': 'Items in Range',
                         'WFItemRangeStart': operand(a), 'WFItemRangeEnd': operand(b)}, 'Items from List')

    def append(self, var, val):
        self.add('is.workflow.actions.appendvariable', {'WFVariableName': var, 'WFInput': att(self.lit(val))})

    def count(self, x):
        return self.add('is.workflow.actions.count', {'Input': att(x), 'WFCountType': 'Items'}, 'Count')

    def avg(self, x):
        return self.add('is.workflow.actions.statistics',
                        {'Input': att(x), 'WFStatisticsOperation': 'Average'}, 'Average')

    # text
    def replace(self, x, find, repl, regex=True):
        return self.add('is.workflow.actions.text.replace', {
            'WFInput': tok(x), 'WFReplaceTextRegularExpression': regex, 'WFReplaceTextCaseSensitive': True,
            'WFReplaceTextFind': find, 'WFReplaceTextReplace': repl if isinstance(repl, str) else tok(repl)},
            'Updated Text')

    def match(self, x, pattern):
        return self.add('is.workflow.actions.text.match', {'text': tok(x), 'WFMatchTextPattern': pattern,
                                                           'WFMatchTextCaseSensitive': True}, 'Matches')

    def split(self, x, sep):
        return self.add('is.workflow.actions.text.split', {'text': tok(x), 'WFTextSeparator': 'Custom',
                                                           'WFTextCustomSeparator': sep}, 'Split Text')

    # dates
    def now(self):
        return self.add('is.workflow.actions.date', {'WFDateActionMode': 'Current Date'}, 'Date')

    def fmtd(self, d, fmt):
        return self.add('is.workflow.actions.format.date',
                        {'WFDate': tok(d), 'WFDateFormatStyle': 'Custom', 'WFTimeFormatStyle': 'None',
                         'WFDateFormat': fmt}, 'Formatted Date')

    def addd(self, d, mag, unit):
        return self.add('is.workflow.actions.adjustdate',
                        {'WFDate': tok(d), 'WFAdjustOperation': 'Add',
                         'WFDuration': {'Value': {'Unit': unit, 'Magnitude': operand(mag)},
                                        'WFSerializationType': 'WFQuantityFieldValue'}}, 'Adjusted Date')

    def utc(self, d):
        return self.add('is.workflow.actions.converttimezone', {
            'Date': tok(d),
            'DestinationTimeZone': {'alCityIdentifier': 302, 'localizedCityName': 'UTC', 'timeZone': 'GMT'},
            'SourceTimeZone': {'alCityIdentifier': 289, 'localizedCityName': 'Tallinn, Estonia',
                               'timeZone': 'Europe/Tallinn'}}, 'Converted Date')

    # io
    def url(self, *parts):
        return self.add('is.workflow.actions.downloadurl', {'WFURL': tok(*parts), 'ShowHeaders': False},
                        'Contents of URL')

    def getfile(self, path):
        return self.add('is.workflow.actions.documentpicker.open',
                        {'WFGetFilePath': path, 'WFShowFilePicker': False, 'WFFileErrorIfNotFound': False}, 'File')

    def savefile(self, content, path):
        named = self.add('is.workflow.actions.setitemname',
                         {'WFInput': att(content), 'WFName': path, 'WFDontIncludeFileExtension': False},
                         'Renamed Item')
        self.add('is.workflow.actions.documentpicker.save',
                 {'WFInput': att(named), 'WFAskWhereToSave': False, 'WFSaveFileOverwrite': True,
                  'WFFileDestinationPath': path}, 'Saved File')

    def notify(self, title, *body):
        self.add('is.workflow.actions.notification',
                 {'WFNotificationActionTitle': title if isinstance(title, str) else tok(*title),
                  'WFNotificationActionBody': tok(*body), 'WFNotificationActionSound': False}, 'Notification')

    def exit(self):
        self.add('is.workflow.actions.exit', {})

    def run(self, name):
        # Run Shortcut finds the shortcut by name, and an accented name may be stored composed or decomposed.
        assert name.isascii(), name
        return self.add('is.workflow.actions.runworkflow',
                        {'WFWorkflowName': name, 'WFShowWorkflow': False}, 'Shortcut Result')

    def output(self, r):
        self.add('is.workflow.actions.output', {'WFOutput': tok(r)})

    # control flow
    @contextmanager
    def IF(self, inp, op, val=None):
        g = uid()
        p = {'GroupingIdentifier': g, 'WFControlFlowMode': 0}
        if op in NUM_OPS:
            p['WFCondition'] = NUM_OPS[op]
            p['WFInput'] = {'Type': 'Variable', 'Variable': att(as_num(inp))}
            p['WFNumberValue'] = operand(val)
        elif op in TXT_OPS:
            p['WFCondition'] = TXT_OPS[op]
            # Without the text coercion a Dictionary Value input stops the shortcut on the device.
            p['WFInput'] = {'Type': 'Variable', 'Variable': att(as_txt(inp))}
            p['WFConditionalActionString'] = val if isinstance(val, str) else tok(val)
        else:
            p['WFCondition'] = ANY_OPS[op]
            p['WFInput'] = {'Type': 'Variable', 'Variable': att(inp)}
        self.add(C, p)
        yield Branch(self, g)
        self.add(C, {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})

    @contextmanager
    def REPEAT(self, n):
        g = uid()
        self.add('is.workflow.actions.repeat.count',
                 {'GroupingIdentifier': g, 'WFControlFlowMode': 0,
                  'WFRepeatCount': n if isinstance(n, int) else att(n)})
        yield
        self.add('is.workflow.actions.repeat.count', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})

    @contextmanager
    def EACH(self, lst, results):
        # results: list that receives the Repeat Results ref after the block closes
        g = uid()
        self.add('is.workflow.actions.repeat.each', {'GroupingIdentifier': g, 'WFControlFlowMode': 0,
                                                     'WFInput': att(lst)})
        yield
        u = uid()
        self.add('is.workflow.actions.repeat.each', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': u})
        results.append({'OutputName': 'Repeat Results', 'OutputUUID': u, 'Type': 'ActionOutput'})

    @contextmanager
    def MENU(self, prompt, titles):
        g = uid()
        self.add('is.workflow.actions.choosefrommenu', {'GroupingIdentifier': g, 'WFControlFlowMode': 0,
                                                        'WFMenuPrompt': prompt, 'WFMenuItems': titles})

        def case(t):
            self.add('is.workflow.actions.choosefrommenu',
                     {'GroupingIdentifier': g, 'WFControlFlowMode': 1, 'WFMenuItemTitle': t})
        yield case
        self.add('is.workflow.actions.choosefrommenu', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})


def workflow(sc, questions=(), types=('WFWorkflowTypeShowInSearch',), out_classes=()):
    return {
        'WFWorkflowActions': sc.A,
        'WFWorkflowImportQuestions': list(questions),
        'WFWorkflowClientVersion': '4033.0.3.5',
        'WFWorkflowMinimumClientVersion': 900,
        'WFWorkflowMinimumClientVersionString': '900',
        'WFWorkflowIcon': {'WFWorkflowIconStartColor': 4274264319, 'WFWorkflowIconGlyphNumber': 59734},
        'WFWorkflowTypes': list(types),
        'WFWorkflowInputContentItemClasses': [],
        'WFWorkflowOutputContentItemClasses': list(out_classes),
        'WFWorkflowHasOutputFallback': False,
        'WFWorkflowHasShortcutInputVariables': False,
        'WFQuickActionSurfaces': [],
    }


def write(wf, path):
    with open(path, 'wb') as f:
        plistlib.dump(wf, f, fmt=plistlib.FMT_BINARY)
