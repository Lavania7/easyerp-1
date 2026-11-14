"""Auditable one-off legacy import; preview by default, atomic opt-in application.

Uses only the Python standard library and the target project's PostgreSQL adapter.
Source files are never modified. Unknown business facts remain SQL NULL.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

VERSION='legacy2-20261023-v1'
CN=timezone(timedelta(hours=8))

def packed(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(v): return hashlib.sha256(v if isinstance(v,bytes) else v.encode('utf-8')).hexdigest()
def uid(kind,*v): return 'old2-'+kind+'-'+sha(packed(v))[:32]
def clean(v): return None if v is None or not str(v).strip() else str(v).strip()
def number(v):
    v=clean(v)
    if v is None: return None
    d=Decimal(v.replace(',',''))
    if not d.is_finite() or d.as_tuple().exponent < -6: raise ValueError('Invalid numeric source: '+v)
    return format(d,'f')
def timevalue(v):
    v=clean(v)
    if v is None: return None
    v=v.replace('年','-').replace('月','-').replace('日','')
    d=datetime.fromisoformat(v)
    return (d.replace(tzinfo=CN) if d.tzinfo is None else d).isoformat()
def sqlval(v):
    if v is None: return 'NULL'
    # UTF-8 hex avoids psql commands, backslash escapes and quote ambiguities.
    return "convert_from(decode('"+str(v).encode('utf-8').hex()+"','hex'),'UTF8')"
def quote(v): return '"'+v.replace('"','""')+'"'

def xrows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>96*1024*1024: raise ValueError('Oversize workbook')
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(t.text or '' for t in e.findall('.//{*}t')) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={r.get('Id'):r for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        book=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=[]
        for sheet in book.findall('./{*}sheets/{*}sheet'):
            rel=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            if rel.get('TargetMode')=='External': raise ValueError('External worksheet')
            target=rel.get('Target'); target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            if '..' in Path(target).parts: raise ValueError('Unsafe worksheet path')
            rows=[]
            for row in ET.fromstring(z.read(target)).findall('.//{*}sheetData/{*}row'):
                cells={}
                for c in row:
                    col=0
                    for a in ''.join(a for a in c.get('r','') if a.isalpha()): col=col*26+ord(a.upper())-64
                    v=c.find('{*}v'); v=v.text if v is not None else None
                    if c.find('{*}f') is not None: raise ValueError('Formula in source export')
                    if c.get('t')=='s': v=shared[int(v)] if v is not None else None
                    elif c.get('t')=='inlineStr': v=''.join(t.text or '' for t in c.findall('.//{*}t'))
                    if col: cells[col]=v
                rows.append((int(row.get('r')), [cells.get(i) for i in range(1,max(cells,default=0)+1)]))
            sheets.append((sheet.get('name'),rows))
        if len(sheets)!=1: raise ValueError('Expected one source worksheet')
        return sheets[0]

def textrows(raw):
    for enc in ('utf-8-sig','gb18030'):
        try: return enc,list(enumerate(csv.reader(io.StringIO(raw.decode(enc),newline=''),strict=True),1))
        except UnicodeError: pass
    raise ValueError('Unsupported text encoding')

class Plan:
    def __init__(self,source,project):
        self.source=source.resolve(); self.project=project.resolve()
        self.files=[]; self.rows=[]; self.issues=[]; self.tables=defaultdict(dict)
        self.orders=defaultdict(list); self.funds={}; self.controls=[]; self.account_totals=defaultdict(lambda:Counter())
        self.catalog=json.loads((project/'app/import_formats.json').read_text(encoding='utf-8'))
        self.profiles={t['id']:t['profiles'] for t in self.catalog['types']}

    def issue(self,code,detail,file=None,row=None,order=None):
        self.issues.append({'id':uid('issue',code,file,row,order,detail),'code':code,'detail':detail,'file_id':file,'row_no':row,'order_id':order})

    def add(self,table,row):
        key=next(iter(row.values()))
        if key in self.tables[table] and self.tables[table][key]!=row: raise ValueError('Conflicting generated record: '+table+'/'+key)
        self.tables[table][key]=row
        return key

    def read(self):
        paths=sorted(p for area in ('finance','sales') for p in (self.source/area).rglob('*') if p.is_file())
        if not paths: raise ValueError('No input files')
        for path in paths:
            raw=path.read_bytes(); rel=path.relative_to(self.source).as_posix(); fid=uid('file',rel,sha(raw))
            kind='sales-orders' if path.parent.name=='sales' else 'bank-history' if path.name.startswith('historydetail') else 'aggregate-settlement' if path.name.startswith('2220072947975_') else 'alipay-summary' if '汇总' in path.name else 'alipay-detail' if '账务明细' in path.name else 'deposit-ledger' if path.suffix=='.csv' else 'note'
            f={'file_id':fid,'relative_path':rel,'sha256':sha(raw),'size_bytes':len(raw),'format_id':kind,'encoding':None,'sheet':None,'header':None,'metadata':{},'data_rows':0}
            self.files.append(f)
            if kind=='note':
                text=raw.decode('utf-8-sig')
                self.rows.append({'file_id':fid,'sheet':'','row_no':1,'kind':'note','values':[text],'mapped':{}})
                f['metadata']['text']=text
                continue
            if path.suffix=='.xlsx': sheet,rows=xrows(raw)
            else: f['encoding'],rows=textrows(raw); sheet=''
            profiles=[p for p in self.profiles[kind] if (p.get('sheet','')==sheet and next((v for n,v in rows if n==p['header_row']),[])==p['columns'])]
            if len(profiles)!=1: raise ValueError('Unregistered or ambiguous source layout: '+rel)
            profile=profiles[0]; f['profile']=profile['id']; f['sheet']=sheet; f['header']=profile['columns']
            for n,markers in profile.get('markers',{}).items():
                if next((v for rn,v in rows if rn==int(n)),[])!=markers: raise ValueError('Source marker changed: '+rel)
            data=[]
            for n,values in rows:
                is_data=n>profile['header_row'] and len(values)>1 and any(clean(v) for v in values) and not str(values[0] or '').startswith('#')
                if any(clean(v) for v in values[len(f['header']):]): raise ValueError('Unregistered body columns: '+rel)
                rr={'file_id':fid,'sheet':sheet,'row_no':n,'kind':'summary' if is_data and kind=='alipay-summary' else 'detail' if is_data else 'metadata','values':values,'mapped':{}}
                self.rows.append(rr)
                if is_data:
                    d={h:clean(values[i]) if i<len(values) else None for i,h in enumerate(f['header'])}
                    data.append((rr,d))
            f['data_rows']=len(data)
            if kind.startswith('alipay'):
                alltext='\n'.join(str(v or '') for _,vals in rows for v in vals)
                exported=re.search(r'#导出时间：\[([^\]]+)\]',alltext)
                if exported: f['metadata']['exported_at']=timevalue(exported[1])
                dates=re.search(r'#起始日期：\[([^\]]+)\]\s*终止日期：\[([^\]]+)\]',alltext)
                if dates:
                    f['metadata']['start']=timevalue(dates[1])[:10]
                    f['metadata']['end']=(datetime.fromisoformat(timevalue(dates[2]))-timedelta(days=1)).date().isoformat()
                acct=re.search(r'#账号：\[([^\]]+)\]',alltext)
                if not acct: raise ValueError('Missing source account: '+rel)
                f['metadata']['source_account']=acct[1]
            if kind=='sales-orders': self.sales(f,data)
            elif kind=='alipay-summary': self.summary(f,data)
            else: self.finance(f,data)
        self.finish_sales()
        self.reconcile_alipay()
        self.issue('主体资料缺失','源文件没有公司主体及统一社会信用代码，4 个资金账户的主体ID留空；不生成虚构公司。')
        self.issue('币种缺失','网银文件及销售订单文件未明确币种，网银账户和销售订单币种留空；支付宝、聚合结算和保证金按来源中的元/CNY记为CNY。')
        self.issue('导出时间缺失','网银、聚合结算、保证金和销售订单未提供导出时间，留空；不使用文件修改时间代替。')
        self.issue('销售行字段缺失','产品版本、计量单位、原始单价、折扣和取消数量缺失时留空；客户身份、店铺标识和销售平台名称不根据收货地址或开票抬头推断。')
        self.issue('资金归属待核','仅导入逐笔收支，不确认收入、成本、用途、内部划转、重复事件或会计凭证；各账户流水合计不是经营收入。')
        return self

    def finance(self,f,data):
        kind=f['format_id']; aid=uid('account',kind)
        names={'bank-history':('企业网银账户','企业网银','银行账户'), 'aggregate-settlement':('企业聚合结算账户','聚合结算渠道','聚合结算账户'), 'alipay-detail':('企业支付宝账户','支付宝','支付账户'), 'deposit-ledger':('保证金账户','淘宝保证金','保证金账户')}
        name,platform,nature=names[kind]
        self.add('finance.资金账户档案表',{'账户ID':aid,'账户名':name,'主体ID':None,'平台':platform,'币种':None if kind=='bank-history' else 'CNY','账户性质':nature,'余额来源':str(self.source/'finance')})
        dates=[]; ins=Decimal(0); outs=Decimal(0); seen=set()
        for rr,d in data:
            if kind=='bank-history':
                when=d['交易时间']; inc=number(d['贷方发生额']); exp=number(d['借方发生额'])
                if d['借/贷'] not in ('借','贷'): raise ValueError('Unknown bank direction')
                txn=re.search(r'指令编号：\s*(\S+)',d['个性化信息'] or '')
                txn=txn[1] if txn else None
                sourcekey=packed(d); desc='；'.join(d[k] for k in ('摘要','用途','对方单位名称') if d[k])
                f['metadata']['source_account']=d['本方账号']
            elif kind=='aggregate-settlement':
                when=d['入帐时间']; inc=number(d['收入金额(元)']); exp=number(d['支出金额(元)']); txn=d['支付流水号']; sourcekey=txn
                desc='；'.join(d[k] for k in ('入帐类型','业务描述','备注') if d[k]); f['metadata']['source_account']=d['商家昵称']
            elif kind=='alipay-detail':
                when=d['发生时间']; inc=number(d['收入金额（+元）']); exp=number(d['支出金额（-元）']); txn=d['账务流水号']; sourcekey=txn
                desc='；'.join(d[k] for k in ('业务类型','商品名称','备注','对方账号') if d[k])
            else:
                when=d['完成时间']; signed=Decimal(number(d['收支金额(元)'])); inc=str(signed) if signed>0 else None; exp=str(-signed) if signed<0 else None
                txn=d['业务编号']; sourcekey=packed(d); desc='；'.join(d[k] for k in ('操作类型','原因','业务描述','订单编号') if d[k])
            i=abs(Decimal(inc)) if inc is not None else Decimal(0); o=abs(Decimal(exp)) if exp is not None else Decimal(0)
            if bool(i)==bool(o): raise ValueError('Ambiguous or zero finance movement '+f['relative_path']+':'+str(rr['row_no']))
            if kind=='bank-history' and (d['借/贷']=='借')!=bool(o): raise ValueError('Bank direction disagreement')
            direction='收入' if i else '支出'; amount=i or o
            if amount.as_tuple().exponent < -4: raise ValueError('Money exceeds schema precision')
            fundid=uid('fund',aid,sourcekey)
            if fundid in seen: raise ValueError('Indistinguishable duplicate inside source file')
            seen.add(fundid)
            row={'资金记录ID':fundid,'账户ID':aid,'发生时间':timevalue(when),'金额':str(amount),'收支方向':direction,'平台交易号':txn,'交易摘要':desc or None}
            if fundid not in self.funds:
                self.account_totals[kind]['rows']+=1; self.account_totals[kind][direction]+=amount
            self.funds[fundid]=row; self.add('finance.资金流水表',row)
            self.add('finance.流水来源明细表',{'流水来源ID':uid('fund-source',f['file_id'],rr['row_no']),'资金记录ID':fundid,'流水文件ID':f['file_id'],'来源行号':rr['row_no']})
            rr['mapped']['资金记录ID']=fundid; dates.append(timevalue(when)[:10]); ins+=i; outs+=o
        if dates:
            f['metadata'].update(actual_start=min(dates),actual_end=max(dates),income=str(ins),expense=str(outs))
        self.add('finance.流水文件登记表',{'流水文件ID':f['file_id'],'账户ID':aid,'导出时间':f['metadata'].get('exported_at'),'覆盖开始日期':f['metadata'].get('start',min(dates) if dates else None),'覆盖结束日期':f['metadata'].get('end',max(dates) if dates else None),'文件路径':str(self.source/f['relative_path']),'文件校验值':f['sha256']})

    def summary(self,f,data):
        totals=[d for _,d in data if d['类型']=='合计']
        if len(totals)!=1: raise ValueError('Missing unique Alipay summary total')
        d=totals[0]
        self.controls.append({'file_id':f['file_id'],'month':f['metadata']['start'][:7],'income':number(d['收入金额（+元）']),'expense':str(abs(Decimal(number(d['支出金额（-元）'])))),'income_rows':int(d['收入笔数']),'expense_rows':int(d['支出笔数'])})

    def sales(self,f,data):
        dates=[]
        for rr,d in data:
            if not d['订单编号'] or not d['订单创建时间']: raise ValueError('Missing order identity')
            self.orders[d['订单编号']].append((f,rr,d)); dates.append(timevalue(d['订单创建时间'])[:10])
        f['metadata'].update(actual_start=min(dates),actual_end=max(dates))
        if 'Q1' in f['relative_path'] and any(int(d[5:7])>3 for d in dates): self.issue('文件季度与内容不符','Q1文件的订单创建日期为'+min(dates)+'至'+max(dates)+'，按内容日期导入，不补造1至3月销售。',f['file_id'])

    def finish_sales(self):
        channel=uid('channel','source-sales-export')
        self.add('sales.渠道档案表',{'渠道ID':channel,'渠道名称':'平台销售订单导出','平台名称':None,'店铺标识':None})
        for f in (f for f in self.files if f['format_id']=='sales-orders'):
            self.add('sales.平台文件登记表',{'平台文件ID':f['file_id'],'渠道ID':channel,'导出时间':None,'覆盖开始日期':f['metadata']['actual_start'],'覆盖结束日期':f['metadata']['actual_end'],'筛选条件':None,'文件路径':str(self.source/f['relative_path']),'文件校验值':f['sha256']})
        for order,versions in sorted(self.orders.items()):
            # Most complete export, then path, only after verifying business values agree.
            versions.sort(key=lambda v:(sum(x is not None for x in v[2].values()),v[0]['relative_path']))
            f,rr,d=versions[-1]; oid=uid('order',channel,order)
            fields=('订单创建时间','订单状态','商品标题','商品属性SKU','宝贝总数量','宝贝种类','买家实付金额','买家应付邮费','退款金额','收货地址','支付单号')
            for field in fields:
                vals={v[2].get(field) for v in versions if v[2].get(field) is not None}
                if len(vals)>1: raise ValueError('Conflicting snapshots require review: '+order+'/'+field)
            status={'交易成功':'已确认','交易关闭':'已关闭'}.get(d['订单状态'],'待确认')
            self.add('sales.销售订单登记表',{'订单ID':oid,'渠道ID':channel,'平台订单号':order,'客户ID':None,'支付单号':d['支付单号'],'创建时间':timevalue(d['订单创建时间']),'币种':None,'状态':status})
            snapshots=[]
            for vf,vr,vd in versions:
                sid=uid('snapshot',vf['file_id'],vr['row_no']); snapshots.append(sid)
                self.add('sales.订单导出快照表',{'订单快照ID':sid,'订单ID':oid,'平台文件ID':vf['file_id'],'来源行号':vr['row_no'],'付款时间':timevalue(vd['订单付款时间']),'原商品标题':vd['商品标题'],'原商品属性':vd['商品属性SKU'],'原始实付':number(vd['买家实付金额']),'原始累计退款':number(vd['退款金额']),'原发货信息':packed({k:vd.get(k) for k in ('应发货时间','发货时间','确认收货时间')}),'原物流信息':packed({k:vd.get(k) for k in ('运送方式','物流单号','物流公司')})})
                vr['mapped'].update(订单ID=oid,订单快照ID=sid)
            if len(versions)>1: self.issue('重复订单快照','同一平台订单保留全部来源快照，共有业务字段一致；订单及商品行只入库一次。',f['file_id'],rr['row_no'],oid)
            count=int(d['宝贝种类']); titles=d['商品标题'].split(',') if count>1 else [d['商品标题']]
            if len(titles)!=count: raise ValueError('Cannot safely split product titles '+order)
            single=count==1; freight=number(d['买家应付邮费']); zero_freight=freight is not None and Decimal(freight)==0
            if not single: self.issue('多商品订单待分配','原始标题可拆分为'+str(count)+'个商品，但没有逐商品数量、金额、运费、子订单及单位对应，相关字段留空。',f['file_id'],rr['row_no'],oid)
            if not zero_freight: self.issue('实付与运费待分配','来源含非零应付邮费，未提供商品实付及运费的实际分配；原始订单实付仍保留在快照。',f['file_id'],rr['row_no'],oid)
            child=re.findall(r'子订单(\d+)[：:]\s*(\d{4}-\d{2}-\d{2})',d.get('应发货时间') or '')
            lids=[]
            for n,title in enumerate(titles,1):
                lid=uid('line',oid,n); lids.append(lid)
                info=title+('；SKU：'+d['商品属性SKU'] if single and d['商品属性SKU'] else '')
                self.add('sales.销售订单行表',{'销售订单行ID':lid,'订单ID':oid,'行号':n,'子订单号':child[0][0] if single and len(child)==1 else None,'原商品信息':info,'产品版本ID':None,'数量':number(d['宝贝总数量']) if single else None,'单位ID':None,'单价':None,'折扣金额':None,'商品实付':number(d['买家实付金额']) if single and zero_freight else None,'运费分摊':freight if single and zero_freight else None,'税额分摊':None,'交期':child[0][1] if single and len(child)==1 else None,'收货信息':d['收货地址'],'来源订单快照ID':snapshots[-1],'取消数量':None,'状态':'待映射'})
            for _,vr,_ in versions: vr['mapped']['销售订单行ID']=lids
        for f in (f for f in self.files if f['format_id']=='sales-orders'):
            self.add('sales.销售期间覆盖表',{'覆盖记录ID':uid('coverage',f['file_id']),'平台文件ID':f['file_id'],'去重规则':'按本批来源渠道与平台订单号去重；所有文件快照保留；重复项共有业务字段须一致。','不可恢复记录说明':'原文件覆盖仅按实际订单创建日期记录，未据季度文件名宣称完整月份。','退款口径':'原始累计退款照录到订单快照，未转为资金事件、售后确认或收入扣减。','未核商品行说明':'产品、单位、单价、折扣、取消数量和多商品逐项分配缺失项均为空。','确认人ID':None})

    def reconcile_alipay(self):
        details={f['metadata']['start'][:7]:f for f in self.files if f['format_id']=='alipay-detail'}
        for c in self.controls:
            f=details[c['month']]; selected=[v for v in self.funds.values() if v['资金记录ID'] in {r['mapped'].get('资金记录ID') for r in self.rows if r['file_id']==f['file_id']}]
            ic=sum(v['收支方向']=='收入' for v in selected); oc=sum(v['收支方向']=='支出' for v in selected)
            ok=Decimal(c['income'])==Decimal(f['metadata']['income']) and Decimal(c['expense'])==Decimal(f['metadata']['expense']) and ic==c['income_rows'] and oc==c['expense_rows']
            c['detail_file_id']=f['file_id']; c['passed']=ok
            if not ok: raise ValueError('Alipay monthly summary does not match details: '+c['month'])

    def report(self):
        manifest=[{k:f[k] for k in ('relative_path','sha256','size_bytes')} for f in self.files]
        return {'version':VERSION,'source_root':str(self.source),'project_root':str(self.project),'manifest_sha256':sha(packed(manifest)),'files':self.files,'table_counts':{t:len(r) for t,r in self.tables.items()},'raw_rows':len(self.rows),'finance_controls':{k:{x:str(v) for x,v in total.items()} for k,total in self.account_totals.items()},'alipay_reconciliation':self.controls,'exceptions':self.issues,'timezone_normalization':'中国境内银行/平台导出中的无时区时间按Asia/Shanghai（UTC+08:00）规范化；原始字符串全部保留。','source_unchanged':all(sha((self.source/f['relative_path']).read_bytes())==f['sha256'] for f in self.files)}

    def sql(self,report):
        # A single transaction includes nullable-field compatibility and all records.
        out=['BEGIN;','SET LOCAL lock_timeout=\'10s\';',"SELECT pg_advisory_xact_lock(hashtext('easyerp-legacy2-import'));",((Path(__file__).resolve().parents[1]/'db'/'imports'/'import_legacy_nulls.sql')).read_text(encoding='utf-8')]
        def insert(table,rows):
            if not rows: return
            cols=list(rows[0]); qualified='.'.join(quote(x) for x in table.split('.')); pk=cols[0]
            for start in range(0,len(rows),100):
                chunk=rows[start:start+100]; values=[]
                for row in chunk:
                    parts=[]
                    for col in cols:
                        v=row.get(col)
                        if isinstance(v,(dict,list)): parts.append(sqlval(packed(v))+'::jsonb')
                        elif isinstance(v,bool): parts.append('TRUE' if v else 'FALSE')
                        elif isinstance(v,int): parts.append(str(v))
                        else: parts.append(sqlval(v))
                    values.append('('+','.join(parts)+')')
                # Explicit casts through a typed JSON record avoid text-to-numeric issues.
                payload=packed(chunk)
                out.append('INSERT INTO '+qualified+' ('+','.join(map(quote,cols))+') SELECT '+','.join(map(quote,cols))+' FROM jsonb_populate_recordset(NULL::'+qualified+','+sqlval(payload)+'::jsonb) ON CONFLICT DO NOTHING;')
                # Never let a conflicting pre-existing key be silently skipped.
                predicates=' OR '.join('t.'+quote(c)+' IS DISTINCT FROM x.'+quote(c) for c in cols if c!=pk)
                if predicates:
                    out.append('DO $check$ BEGIN IF EXISTS(SELECT 1 FROM jsonb_populate_recordset(NULL::'+qualified+','+sqlval(payload)+'::jsonb) x LEFT JOIN '+qualified+' t ON t.'+quote(pk)+'=x.'+quote(pk)+' WHERE t.'+quote(pk)+' IS NULL OR '+predicates+") THEN RAISE EXCEPTION 'Existing import record conflicts with prepared data'; END IF; END $check$;")
        insert('erp_ops.source_import_file',[{'file_id':f['file_id'],'source_root':str(self.source),'relative_path':f['relative_path'],'file_sha256':f['sha256'],'size_bytes':f['size_bytes'],'format_id':f['format_id'],'header':f['header'],'metadata':f['metadata']} for f in self.files])
        order=['finance.资金账户档案表','finance.流水文件登记表','finance.资金流水表','finance.流水来源明细表','sales.渠道档案表','sales.平台文件登记表','sales.销售订单登记表','sales.订单导出快照表','sales.销售订单行表','sales.销售期间覆盖表']
        for table in order: insert(table,list(self.tables[table].values()))
        # Source rows use a generated primary key in addition to their location key.
        insert('erp_ops.source_import_row',[{'row_id':uid('raw',r['file_id'],r['sheet'],r['row_no']),'file_id':r['file_id'],'sheet_name':r['sheet'],'row_no':r['row_no'],'record_type':r['kind'],'raw_values':r['values'],'mapped_ids':r['mapped']} for r in self.rows])
        insert('erp_ops.source_import_exception',[{'exception_id':i['id'],'file_id':i['file_id'],'row_no':i['row_no'],'order_id':i['order_id'],'reason_code':i['code'],'details':i['detail']} for i in self.issues])
        insert('erp_ops.source_import_run',[{'run_id':uid('run',VERSION,report['manifest_sha256']),'importer_version':VERSION,'manifest_sha256':report['manifest_sha256'],'source_manifest':[{k:f[k] for k in ('relative_path','sha256','size_bytes')} for f in self.files],'report':report}])
        out.append((self.project/'tests/structure.sql').read_text(encoding='utf-8'))
        out.append('COMMIT;')
        return '\n'.join(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True); p.add_argument('--project-root',type=Path,required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--apply',action='store_true')
    a=p.parse_args(); plan=Plan(a.source_root,a.project_root).read(); report=plan.report()
    if not report['source_unchanged']: raise RuntimeError('Source changed during preparation')
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'preview.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    script=plan.sql(report); (a.out/'prepared-import.sql').write_text(script,encoding='utf-8')
    if a.apply:
        sys.path.insert(0,str(a.project_root/'tools')); from easyerp import ERP
        e=ERP()
        actual=e.sql("SELECT current_setting('data_directory');").stdout.strip()
        if Path(actual).resolve()!=e.data.resolve(): raise RuntimeError('Connected to unexpected PostgreSQL cluster')
        e.verify_files()
        backup=e.backup(verify_data=True)
        result=e.sql(script)
        report['applied_at_utc']=datetime.now(timezone.utc).isoformat(); report['backup']=str(backup)
        report['structure_check']=e.check()
        report['database_counts']={}
        for table in plan.tables:
            schema,name=table.split('.',1)
            report['database_counts'][table]=int(e.sql('SELECT count(*) FROM '+quote(schema)+'.'+quote(name)+';').stdout.strip())
        report['source_unchanged']=all(sha((plan.source/f['relative_path']).read_bytes())==f['sha256'] for f in plan.files)
        (a.out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('table_counts','raw_rows','source_unchanged')},ensure_ascii=False,indent=2))
    if a.apply: print('COMMITTED; backup: '+report['backup'])

if __name__=='__main__': main()
