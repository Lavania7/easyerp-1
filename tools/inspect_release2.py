from pathlib import Path, PurePosixPath
from collections import Counter
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET

SOURCE=Path(r'D:\projx\demo\easyerp-old1\xlsx\release2.0.xlsx')
OUT=Path('outputs/release2-import-20261023')

def inspect(path=SOURCE):
    raw=path.read_bytes()
    result={'source':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw),'sheets':[]}
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in e.findall('.//{*}t')) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        result['defined_names']=[dict(e.attrib,value=e.text) for e in book.findall('./{*}definedNames/{*}definedName')]
        rels={r.get('Id'):r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in book.findall('./{*}sheets/{*}sheet'):
            rel=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            if rel.get('TargetMode')=='External': raise ValueError('External sheet')
            target=rel.get('Target');target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            if '..' in PurePosixPath(target).parts: raise ValueError('Unsafe target')
            tree=ET.fromstring(z.read(target)); dim=tree.find('{*}dimension')
            info={'name':sheet.get('name'),'state':sheet.get('state'),'dimension':dim.get('ref') if dim is not None else None,'rows':[],'formula_count':0,'error_count':0,'tables':[]}
            for row in tree.findall('./{*}sheetData/{*}row'):
                cells={}
                for c in row:
                    if c.tag.rsplit('}',1)[-1]!='c':continue
                    value=c.find('{*}v');value=value.text if value is not None else None
                    kind=c.get('t','n');formula=c.find('{*}f')
                    if kind=='s': value=shared[int(value)] if value is not None else None
                    elif kind=='inlineStr':value=''.join(t.text or '' for t in c.findall('.//{*}t'))
                    if value is not None or formula is not None:
                        cells[c.get('r')]={'value':value,'type':kind,'style':c.get('s'),'formula':formula.text if formula is not None else None,'formula_meta':dict(formula.attrib) if formula is not None else None}
                        info['formula_count']+=formula is not None;info['error_count']+=kind=='e'
                if cells:info['rows'].append({'row_no':int(row.get('r')),'cells':cells})
            relpath=str(PurePosixPath(target).parent/'_rels'/(PurePosixPath(target).name+'.rels'))
            if relpath in z.namelist():
                for rel in ET.fromstring(z.read(relpath)):
                    if rel.get('Type','').endswith('/table'):
                        path=rel.get('Target');path=path.lstrip('/') if path.startswith('/') else 'xl/'+path.removeprefix('../')
                        table=ET.fromstring(z.read(path));info['tables'].append({'name':table.get('name'),'ref':table.get('ref'),'columns':[c.attrib for c in table.findall('./{*}tableColumns/{*}tableColumn')]})
            result['sheets'].append(info)
    return result

if __name__=='__main__':
    result=inspect();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'workbook-inspection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SHA256',result['sha256'])
    for s in result['sheets']:
        print(json.dumps({k:s[k] for k in ('name','dimension','formula_count','error_count','tables')},ensure_ascii=False))
        print('NONEMPTY_ROWS',len(s['rows']))
        for r in s['rows'][:10]:
            print(json.dumps({'row':r['row_no'],'cells':{k:('='+str(v['formula'])+' => '+str(v['value']) if v['formula'] is not None else v['value']) for k,v in r['cells'].items()}},ensure_ascii=False))
