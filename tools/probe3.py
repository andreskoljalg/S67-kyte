# Builds "Kyte probe 3": repeat counts, loop speed, files, and Run Shortcut by composed name.
import os, sys, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from sc import SC, V, att, tok, workflow, write, uid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = SC()
s.setv('R', 'start')


def rep(name, ref):
    s.append('R', s.text(name, '=', ref))
    s.add('is.workflow.actions.setclipboard', {'WFInput': att(s.text(V('R')))})


def loop(label, count):
    s.setv('k', 0)
    g = uid()
    s.add('is.workflow.actions.repeat.count', {'GroupingIdentifier': g, 'WFControlFlowMode': 0, 'WFRepeatCount': count})
    s.calc('k', V('k'), '+', 1)
    s.add('is.workflow.actions.repeat.count', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})
    rep(label, V('k'))


loop('rep_int', 5)
loop('rep_real', 5.0)
s.setv('N', s.num(5))
loop('rep_var', att(V('N')))
loop('rep_var_num', att(dict(V('N'), Aggrandizements=[{'Type': 'WFCoercionVariableAggrandizement',
                                                        'CoercionItemClass': 'WFNumberContentItem'}])))
s.setv('N', s.get(s.todict(s.text('{"n":5}')), 'n'))
loop('rep_json_var', att(V('N')))

# speed: 100 iterations of a typical body (get item, math, compare, set, append)
lst = s.get(s.todict(s.text('{"l":[1,2,3,4,5,6,7,8,9,10]}')), 'l')
s.setv('L', lst)
s.setv('t0', s.fmtd(s.now(), 'HH:mm:ss.SSS'))
s.setv('acc', 0)
g = uid()
s.add('is.workflow.actions.repeat.count', {'GroupingIdentifier': g, 'WFControlFlowMode': 0, 'WFRepeatCount': 100})
s.setv('i', V('Repeat Index'))
x = s.item(V('L'), 3)
with s.IF(x, '>', 2):
    s.calc('acc', V('acc'), '+', x)
s.append('Q', V('i'))
s.add('is.workflow.actions.repeat.count', {'GroupingIdentifier': g, 'WFControlFlowMode': 2, 'UUID': uid()})
rep('speed100', s.text(V('t0'), ' -> ', s.fmtd(s.now(), 'HH:mm:ss.SSS'), ' acc=', V('acc'), ' q=', s.count(V('Q'))))

s.savefile(s.text('{"probe":1}'), 'kyte-probe.json')
f = s.getfile('kyte-probe.json')
rep('file', s.get(s.todict(f), 'probe'))
rep('run_nfc', s.get(s.run(unicodedata.normalize('NFC', 'Küte seaded')), 'vat'))
s.output(s.text(V('R')))
write(workflow(s), os.path.join(ROOT, 'build', 'Kyte probe 3.wflow'))
print(len(s.A), 'actions')
