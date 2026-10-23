"""Confirmed missing values and transactional, non-clearing CSV merges."""
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import uuid

from data import I,L
from entry import ManualEntry,EntryError,qualified,text_sql
from imports import ImportError,MAX_CELLS
from standard_templates import FORMAT_VERSION

TYPE_ID='standard-master'
POLICY_VERSION='csv-merge-v2'
MAX_IMPORT_ROWS=5000
BLANK_CHARS=' \t\n\r\f\v\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def shape_signature(obj):
    # Required flags may be relaxed for confirmed gaps; column identity and types stay fixed.
    return digest({'pk':obj['pk'],'columns':[(c['name'],c['type'],c['automatic']) for c in obj['columns']]})


class StandardImport:
    def __init__(self,mode='live'):
        self.entry=ManualEntry({'mode':mode})
        self._missing_support=None

    def missing_support(self):
        if self._missing_support is None:
            self._missing_support=self.entry.data.rows("SELECT to_regprocedure('erp_ops.csv_allow_missing_fields(regclass,text[],text)') IS NOT NULL AS enabled")[0]['enabled']
        return self._missing_support

    @staticmethod
    def needs_missing_support(obj,missing):
        if any(c['required'] and c['name'] in missing for c in obj['columns']):return True
        for rule in obj.get('checks',[]):
            match=re.fullmatch(r'CHECK\s*\(\s*\(*num_nonnulls\(([^()]*)\)\s*=\s*1\s*\)*\s*\)',rule['expression'])
            if match:
                fields=[name.replace('""','"') for name in re.findall(r'"((?:[^"]|"")*)"',match[1])]
                if fields and all(field in missing for field in fields):return True
        return False

    def registration(self):
        objects=list(self.entry.catalog().values())
        return {'id':TYPE_ID,'name':'标准主录表','module':'全部部门',
                'description':'CSV空缺经确认后导入；已有记录可选择使用最新非空值，或只补填原空白项。每批最多5000条。',
                'immutable':True,'enabled':True,'version':0,'updated_at':None,
                'registered_at':'2026-10-23T00:00:00+00:00','sample_count':0,
                'policy_version':POLICY_VERSION,
                'profiles':[{'id':obj['key'],'name':obj['name'],'container':'csv','header_row':1,
                             'columns':[c['name'] for c in obj['columns']],'signature':shape_signature(obj)} for obj in objects]}

    def plan(self,filename,raw,import_key=None):
        if Path(filename).suffix.lower()!='.csv':return None
        file_hash=sha256(raw).hexdigest()
        import_key=import_key or uuid.uuid4().hex
        if not isinstance(import_key,str) or not re.fullmatch('[0-9a-f]{32}',import_key):
            raise ImportError('检查记录已过期，请重新检查文件。',409)
        text=None
        for encoding in ('utf-8-sig','gb18030'):
            try:text=raw.decode(encoding);break
            except UnicodeError:pass
        if text is None or '\x00' in text:raise ImportError('CSV需要使用UTF-8或GB18030编码。')
        try:
            reader=csv.reader(io.StringIO(text,newline=''),strict=True)
            headers=next(reader,[]);catalog=self.entry.catalog();named=catalog.get(Path(filename).stem)
            matches=[obj for obj in catalog.values() if headers==[c['name'] for c in obj['columns']]]
            if named and named not in matches:raise ImportError('标准CSV表头与主录表不一致，请重新下载模板并保留列名与顺序。')
            if named:obj=named
            elif len(matches)==1:obj=matches[0]
            elif len(matches)>1:raise ImportError('此表头对应多张主录表，请保留下载时的“部门.主录表名.csv”文件名。')
            else:return None
            source=[];cells=len(headers);last_line=reader.line_num;skipped=0
            for values in reader:
                line,last_line=last_line+1,reader.line_num;cells+=len(values)
                if cells>MAX_CELLS:raise ImportError('CSV内容过多，请拆分后导入。',413)
                if not values or not any(value.strip() for value in values):skipped+=1;continue
                # Omitted trailing cells and surplus empty cells are blank data, not a new schema.
                while len(values)>len(headers) and not values[-1].strip():values.pop()
                values+=['']*max(0,len(headers)-len(values))
                source.append({'line':line,'values':values})
                if len(source)>MAX_IMPORT_ROWS:raise ImportError('标准CSV每批最多5000条记录，请拆分后导入。',413)
        except csv.Error as exc:raise ImportError('CSV分隔符或引号不完整。') from exc

        errors=[];prepared=[];seen=set();blank_cells=0;blank_rows=0;missing=[];generated=0;preview=[]
        for row in source:
            line,values=row['line'],row['values'];record=dict(zip(headers,values))
            blank=[c['name'] for c in obj['columns'] if not c['automatic'] and not record.get(c['name'],'').strip()]
            blank_cells+=len(blank);blank_rows+=bool(blank)
            if blank and len(missing)<20:missing.append({'line':line,'fields':blank})
            if len(preview)<3:preview.append({'line':line,'values':record.copy()})
            try:
                if len(values)!=len(headers):raise EntryError('列数与表头不一致。')
                if not record[obj['pk']].strip():
                    record[obj['pk']]='CSV-'+digest({'mode':self.entry.mode,'object':obj['key'],'file':file_hash,'line':line})[:40];generated+=1
                    if len(preview)<=3 and preview and preview[-1]['line']==line:preview[-1]['generated_id']=record[obj['pk']]
                if record[obj['pk']] in seen:raise EntryError('文件中存在重复主键「'+obj['pk']+'」。')
                seen.add(record[obj['pk']]);validated={}
                for column in obj['columns']:
                    name=column['name'];value=record[name]
                    if column['automatic']:
                        if value.strip():raise EntryError('系统生成字段「'+name+'」应留空。')
                        continue
                    # Unknown business facts stay NULL; no defaults or zero substitutions.
                    validated[name]=None if not value.strip() else self.entry.value({**column,'required':False},value)
                key=validated[obj['pk']]
                if len(key)>150 or re.search(r'[\x00-\x1f]',key):raise EntryError('记录编号过长或包含控制字符。')
                prepared.append({'line':line,'values':validated})
            except EntryError as exc:
                if len(errors)<20:errors.append('第'+str(line)+'行：'+str(exc))
        signature=shape_signature(obj)
        return {'object':obj,'signature':signature,'rows':prepared,'row_count':len(source),'errors':errors,
                'encoding':encoding,'preview':preview,'blank_cells':blank_cells,'blank_rows':blank_rows,
                'missing':missing,'generated_id_count':generated,'skipped_empty_rows':skipped,
                'match':{'type_id':TYPE_ID,'type_name':'标准主录表','profile':obj['key'],'profile_name':obj['name'],
                         'sheet':'','header_row':1,'columns':headers,'object':obj['key'],'signature':signature},
                'sha256':file_hash,'filename':filename,'import_key':import_key,
                'request_id':'csv2-'+digest({'mode':self.entry.mode,'object':obj['key'],'import_key':import_key})}

    def existing_count(self,plan):
        if not plan['rows']:return 0
        obj=plan['object']
        values=','.join(text_sql(row['values'][obj['pk']]) for row in plan['rows'])
        return self.entry.data.rows('SELECT count(*) AS n FROM '+qualified(obj)+' WHERE '+I(obj['pk'])+' IN ('+values+')')[0]['n']

    def action_hash(self,plan,check_id,merge,allow_incomplete):
        return digest({'mode':self.entry.mode,'object':plan['object']['key'],'sha256':plan['sha256'],
                       'signature':plan['signature'],'check_id':check_id,'import_key':plan['import_key'],
                       'merge':merge,'allow_incomplete':allow_incomplete,'policy':POLICY_VERSION})

    def previous(self,plan,check_id,merge,allow_incomplete):
        rows=self.entry.data.rows('SELECT payload_hash,result FROM erp_ops.frontend_entry_audit WHERE request_id='+L(plan['request_id']))
        if not rows:return None
        if rows[0]['payload_hash'].strip()!=self.action_hash(plan,check_id,merge,allow_incomplete):
            raise ImportError('本次导入的选择已变化，请重新检查文件后再导入。',409)
        return rows[0]['result']

    def inspect(self,plan):
        existing=self.existing_count(plan) if not plan['errors'] else 0
        validations={}
        for merge in ('latest','fill_empty'):
            errors=list(plan['errors'])
            if not errors and plan['row_count']:
                if merge=='fill_empty' and not existing:errors=list(validations['latest'])
                else:
                    try:self.write(plan,merge=merge,allow_incomplete=True,trial=True)
                    except ImportError as exc:errors.append(str(exc))
            validations[merge]=errors
        valid=any(not errors for errors in validations.values())
        return {'status':'recognized','match':plan['match'],'encoding':plan['encoding'],
                'sheets':[{'name':'','physical_rows':plan['row_count']+plan['skipped_empty_rows']+1}],
                'row_count':plan['row_count'],'preview':plan['preview'],'validation_errors':plan['errors'] or ([] if valid else validations['latest']),
                'merge_validation':validations,'validated':valid,'execution':None,'execution_available':True,
                'can_execute':bool(valid and plan['row_count']),'import_key':plan['import_key'],'import_policy_version':POLICY_VERSION,
                'blank_cells':plan['blank_cells'],'blank_rows':plan['blank_rows'],'missing':plan['missing'],
                'generated_id_count':plan['generated_id_count'],'existing_count':existing,'skipped_empty_rows':plan['skipped_empty_rows'],
                'requires_incomplete_confirmation':bool(plan['blank_cells']),'requires_merge_confirmation':bool(existing),
                'reason':'；'.join(plan['errors'] or validations['latest']) if not valid else
                         '模板只有表头，请从第2行填写业务记录。' if not plan['row_count'] else
                         '检查到表信息不全，是否还要导入？' if plan['blank_cells'] else '格式和业务校验通过。'}

    def write(self,plan,check_id=None,merge=None,allow_incomplete=False,trial=False):
        if plan['errors'] or not plan['row_count']:raise ImportError('CSV没有可导入的有效记录。')
        if not trial and plan['blank_cells'] and not allow_incomplete:
            raise ImportError('检查到表信息不全，是否还要导入？',409)
        obj=plan['object'];request=plan['request_id'];payload_hash=self.action_hash(plan,check_id,merge,allow_incomplete)
        sql=["BEGIN; SET LOCAL statement_timeout='30s'; SET LOCAL lock_timeout='4s'; SET LOCAL standard_conforming_strings=on;",
             "DO $csv$ DECLARE saved jsonb; old jsonb; changes jsonb := '[]'::jsonb; records jsonb := '[]'::jsonb; patterns jsonb := '{}'::jsonb; existing_hash text; line_no integer; operation text; created integer := 0; updated integer := 0; unchanged integer := 0; BEGIN",
             f'PERFORM pg_advisory_xact_lock(hashtextextended({L("standard-csv:"+obj["key"])},0));']
        if not trial:
            sql += [f'SELECT payload_hash INTO existing_hash FROM erp_ops.frontend_entry_audit WHERE request_id={L(request)};',
                    f"IF FOUND THEN IF existing_hash<>{L(payload_hash)} THEN RAISE EXCEPTION 'request_reused' USING ERRCODE='22023'; END IF; RETURN; END IF;"]
        columns={c['name']:c for c in obj['columns']}
        for row in plan['rows']:
            values=row['values'];key=text_sql(values[obj['pk']])
            expressions={name:'NULL' if value is None else '('+text_sql(value)+')::'+columns[name]['type'] for name,value in values.items()}
            sql += [f"line_no := {row['line']}; old := NULL;",
                    f'SELECT to_jsonb(t) INTO old FROM {qualified(obj)} t WHERE {I(obj["pk"])}={key} FOR UPDATE;',
                    'IF FOUND THEN']
            if merge is None:sql.append("RAISE EXCEPTION 'csv_merge_confirmation_required' USING ERRCODE='22023';")
            assignments={}
            for name,value in values.items():
                if name==obj['pk'] or value is None:continue
                expression=expressions[name]
                if merge=='fill_empty':
                    empty='t.'+I(name)+' IS NULL'
                    if columns[name]['type']=='text' or columns[name]['type'].startswith('character'):
                        empty+=' OR btrim(t.'+I(name)+','+text_sql(BLANK_CHARS)+")=''"
                    expression='CASE WHEN '+empty+' THEN '+expression+' ELSE t.'+I(name)+' END'
                assignments[name]=expression
            if assignments:
                changed=' OR '.join('t.'+I(name)+' IS DISTINCT FROM ('+expression+')' for name,expression in assignments.items())
                sql += [f'UPDATE {qualified(obj)} AS t SET '+','.join(I(name)+'='+expression for name,expression in assignments.items())+f' WHERE t.{I(obj["pk"])}={key} AND ('+changed+') RETURNING to_jsonb(t) INTO saved;',
                        "IF FOUND THEN operation := 'update'; ELSE saved := old; operation := 'unchanged'; END IF;"]
            else:sql.append("saved := old; operation := 'unchanged';")
            sql.append('ELSE')
            missing=[name for name,value in values.items() if value is None and name!=obj['pk']]
            if missing and self.needs_missing_support(obj,missing):
                pattern=digest(missing)
                if self.missing_support():
                    sql += [f'IF NOT (patterns ? {L(pattern)}) THEN',
                            'PERFORM erp_ops.csv_allow_missing_fields('+L(qualified(obj))+'::regclass,ARRAY['+','.join(L(name) for name in missing)+']::text[],'+L(request)+');',
                            f'patterns := patterns || jsonb_build_object({L(pattern)},true); END IF;']
                else:
                    sql.append("RAISE EXCEPTION 'csv_missing_support_required' USING ERRCODE='22023';")
            sql += [f'INSERT INTO {qualified(obj)} AS t ('+','.join(I(name) for name in values)+') VALUES ('+','.join(expressions.values())+') RETURNING to_jsonb(t) INTO saved;',
                    "operation := 'create'; END IF;",
                    "IF operation='create' THEN created := created+1; ELSIF operation='update' THEN updated := updated+1; ELSE unchanged := unchanged+1; END IF;"]
            if not trial:
                sql += [f"records := records || jsonb_build_array(jsonb_build_object('id',saved->{L(obj['pk'])},'line',line_no,'operation',operation));",
                        f"changes := changes || jsonb_build_array(jsonb_build_object('object',{L(obj['key'])},'line',line_no,'operation',operation,'before',old,'after',saved));"]
        sql += ['line_no := NULL;','SET CONSTRAINTS ALL IMMEDIATE;']
        if not trial:
            result={'request_id':request,'mode':self.entry.mode,'object':obj['key'],'filename':plan['filename'],'sha256':plan['sha256'],
                    'check_id':check_id,'rows_imported':plan['row_count'],'format':FORMAT_VERSION,'signature':plan['signature'],
                    'merge':merge,'allow_incomplete':allow_incomplete,'import_policy_version':POLICY_VERSION,
                    'blank_cells':plan['blank_cells'],'generated_id_count':plan['generated_id_count']}
            sql.append('INSERT INTO erp_ops.frontend_entry_audit(request_id,payload_hash,source,changes,result) VALUES ('+
                       ','.join([L(request),L(payload_hash),"'local_frontend_standard_csv'",'changes',
                                 text_sql(json.dumps(result,ensure_ascii=False))+"::jsonb || jsonb_build_object('records',records,'created',created,'updated',updated,'unchanged',unchanged,'imported_at',clock_timestamp())"])+');')
        sql += ["EXCEPTION WHEN OTHERS THEN RAISE EXCEPTION 'standard_import_row:%:%',coalesce(line_no::text,'batch'),SQLERRM USING ERRCODE=SQLSTATE; END $csv$;"]
        if trial:sql += ["SELECT '{}'::json;",'ROLLBACK;']
        else:sql += [f'SELECT result FROM erp_ops.frontend_entry_audit WHERE request_id={L(request)};','COMMIT;']
        response=self.entry.data.erp.sql('\\set VERBOSITY verbose\n'+'\n'.join(sql),db=self.entry.db,role='easyerp_app',ok=False)
        if response.returncode:
            if 'csv_missing_support_required' in response.stderr:
                raise ImportError('新增记录含数据库必填空缺，需要授权启用空缺数据支持后才能导入。',409)
            if 'csv_merge_confirmation_required' in response.stderr:
                raise ImportError('目标数据已变化，请重新检查并确认是否使用最新一次的数据。',409)
            try:self.entry.db_error(response.stderr)
            except EntryError as exc:
                match=re.search(r'standard_import_row:(\d+):',response.stderr)
                raise ImportError(('第'+match[1]+'行：' if match else '')+str(exc),exc.status) from exc
        return json.loads(response.stdout.strip())
