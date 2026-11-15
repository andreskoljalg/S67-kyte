# Builds "Küte test", a probe shortcut that checks risky encodings on a real device.
# Each result is appended to R and copied to the clipboard, so a crash still shows how far it got.
import os, sys, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from sc import SC, V, att, tok, workflow, write, uid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT = [{'Type': 'WFCoercionVariableAggrandizement', 'CoercionItemClass': 'WFStringContentItem'}]
s = SC()
s.setv('R', 'start')


def rep(name, ref):
    s.append('R', s.text(name, '=', ref))
    s.add('is.workflow.actions.setclipboard', {'WFInput': att(s.text(V('R')))})


def x100(ref):
    return s.math(ref, '×', '100')


m = s.get(s.todict(s.text('{"a":4.58,"m":"ON"}')), 'm')
s.setv('r', 'no')
g = uid()
s.add('is.workflow.actions.conditional', {
    'GroupingIdentifier': g, 'WFControlFlowMode': 0, 'WFCondition': 4, 'WFConditionalActionString': 'ON',
    'WFInput': {'Type': 'Variable', 'Variable': att(dict(m, Aggrandizements=TXT))}})
s.setv('r', 'yes')
s.add('is.workflow.actions.conditional', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})
rep('is_coerced', V('r'))


def cond(label, inp, code, val=None, num=None):
    s.setv('r', 'no')
    g = uid()
    p = {'GroupingIdentifier': g, 'WFControlFlowMode': 0, 'WFCondition': code,
         'WFInput': {'Type': 'Variable', 'Variable': att(inp)}}
    if val is not None:
        p['WFConditionalActionString'] = val
    if num is not None:
        p['WFNumberValue'] = num
    s.add('is.workflow.actions.conditional', p)
    s.setv('r', 'yes')
    s.add('is.workflow.actions.conditional', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})
    rep(label, V('r'))


NUMC = [{'Type': 'WFCoercionVariableAggrandizement', 'CoercionItemClass': 'WFNumberContentItem'}]
jd = s.todict(s.text('{"m":"ASK1","n":2}'))
cond('begins_coerced', dict(s.get(jd, 'm'), Aggrandizements=TXT), 8, 'ASK')
cond('contains_coerced', dict(s.get(jd, 'm'), Aggrandizements=TXT), 99, 'SK')
cond('num_gt_coerced', dict(s.get(jd, 'n'), Aggrandizements=NUMC), 2, num='1')
cond('has_value', s.get(jd, 'm'), 100)
cond('no_value', s.get(jd, 'zz'), 101)
cond('is_text_action', s.text('ON'), 4, 'ON')

t0 = s.fmtd(s.now(), 'HH:mm:ss.SSS')
s.setv('t0', t0)
s.setv('k', 0)
with s.REPEAT(200):
    s.calc('k', V('k'), '+', 1)
rep('loop200', s.text(V('t0'), ' -> ', s.fmtd(s.now(), 'HH:mm:ss.SSS'), ' k=', V('k')))

el = s.text('{"data":{"ee":[{"timestamp":1,"price":12.5},{"timestamp":2,"price":-3.25},'
            '{"timestamp":3,"price":100}]}}')
rx = s.add('is.workflow.actions.text.replace', {
    'WFInput': tok(el), 'WFReplaceTextRegularExpression': True, 'WFReplaceTextCaseSensitive': True,
    'WFReplaceTextFind': r'\{"timestamp":\d+,"price":(-?[0-9.]+)\}', 'WFReplaceTextReplace': '$1'},
    'Updated Text')
rep('regex', rx)
lst = s.get(s.get(s.todict(rx), 'data'), 'ee')
rep('regex_avg', x100(s.avg(lst)))
rep('range', s.text(s.items(lst, 2, 3)))
rep('count', s.count(lst))
rep('item2', s.item(lst, 2))
rep('floor', s.floor(s.num(27)))
rep('floor_div', s.floor(s.math(s.num(27), '÷', '10')))
rep('add_hr', s.fmtd(s.addd(s.now(), 1, 'hr'), 'yyyy-MM-dd HH:mm'))
rep('add_day', s.fmtd(s.addd(s.now(), 1, 'days'), 'yyyy-MM-dd HH:mm'))
s.setv('D', s.emptydict())
s.dset('D', 'x', 'ON')
s.dset('D', 'y', 'OFF')
rep('dset', s.text(V('D')))
sp = s.add('is.workflow.actions.text.split', {'text': tok(s.text('ON|kallis tund|12,5')),
                                                'WFTextSeparator': 'Custom', 'WFTextCustomSeparator': '|'},
           'Split Text')
rep('split2', s.item(sp, 2))
mt = s.add('is.workflow.actions.text.match', {'text': tok(s.text('a:ON b:OFF c:ON')),
                                                'WFMatchTextPattern': '(?<=:)ON', 'WFMatchTextCaseSensitive': True},
           'Matches')
rep('match_count', s.count(mt))
rep('run_nfd', s.get(s.run(unicodedata.normalize('NFD', 'Küte seaded')), 'vat'))
s.setv('mv', s.get(s.todict(s.text('{"m":"ON"}')), 'm'))
s.setv('r', 'no')
with s.IF(V('mv'), 'is', 'ON'):
    s.setv('r', 'yes')
rep('is_var', V('r'))
rep('run_nfc', s.get(s.run(unicodedata.normalize('NFC', 'Küte seaded')), 'vat'))
s.output(s.text(V('R')))

write(workflow(s), os.path.join(ROOT, 'build', 'Kyte probe 2.wflow'))
print(len(s.A), 'actions')
