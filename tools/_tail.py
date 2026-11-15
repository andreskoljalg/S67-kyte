def build_valik():
    s = SC()
    s.comment('Küte valik – answer the approval question with more choices than the reminder gives.\n'
              'Applies to the hours that Küte plaan marked as needing approval.')
    with s.MENU('Kallid tunnid, mis vajavad kinnitust:', ['Küta kõik küsitud tunnid', 'Küta ainult 1 odavaim tund',
                                                           'Ära küta', 'Tühista valik (kasuta meeldetuletust)']) as case:
        for title, val in (('Küta kõik küsitud tunnid', 'all'), ('Küta ainult 1 odavaim tund', 'one'),
                           ('Ära küta', 'none'), ('Tühista valik (kasuta meeldetuletust)', 'reset')):
            case(title)
            s.setv('v', val)
    tallinn_now(s)
    with s.MENU('Mis päevaks?', ['Täna', 'Homme']) as case:
        case('Täna')
        s.setv('dd', s.fmtd(V('now'), 'yyyy-MM-dd'))
        case('Homme')
        s.setv('dd', s.fmtd(s.addd(V('now'), 1, 'days'), 'yyyy-MM-dd'))
    s.setv('VD', s.emptydict())
    f = s.getfile(VALIK_FILE)
    with s.IF(f, 'has'):
        s.setv('VD', s.todict(f))
    s.dset('VD', V('dd'), V('v'))
    s.savefile(s.text(V('VD')), VALIK_FILE)
    s.notify('Küte valik salvestatud', V('dd'), ': ', V('v'), '. Rakendub järgmisel täistunnil.')
    return workflow(s, types=('Watch', 'WFWorkflowTypeShowInSearch'))


if __name__ == '__main__':
    out = os.path.join(ROOT, 'build')
    # (glyph, colour) per shortcut: Shortcuts' own icon numbers
    icons = {SETTINGS_NAME: (59743, 3031607807),      # gear, gray
             'Küte plaan': (61510, 2846468607),       # calendar with plus, taupe
             'S67 Küte (uus)': (59734, 4274264319),   # flame, yellow
             'Kyte test run': (61581, 4292093695),    # sparkles, green
             'Küte valik': (59703, 2071128575)}       # question mark, violet
    for name, fn in ((SETTINGS_NAME, build_settings), ('Küte plaan', build_plan),
                     ('S67 Küte (uus)', build_run), ('Kyte test run', lambda: build_run(dry=True)),
                     ('Küte valik', build_valik)):
        wf = fn()
        glyph, colour = icons[name]
        wf['WFWorkflowIcon'] = {'WFWorkflowIconStartColor': colour, 'WFWorkflowIconGlyphNumber': glyph}
        write(wf, os.path.join(out, name + '.wflow'))
        print(name, len(wf['WFWorkflowActions']), 'actions')
