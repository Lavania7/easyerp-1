"""File workflow contract tests, entirely inside a temporary directory."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from workspace import Workspace,WorkspaceError
from workspace_rules import presentation


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ws=Workspace('demo',self.temp.name)

    def save(self,**kwargs):
        return self.ws.save({'request_id':uuid.uuid4().hex,**kwargs})['item']

    def test_lifecycle_conflict_and_retries(self):
        payload={'request_id':'retry_request_1','kind':'workflow','values':{'title':'流程验收','due':'2026-11-30'}}
        first=self.ws.save(payload)
        self.assertEqual(first,self.ws.save(payload))
        with self.assertRaises(WorkspaceError):self.ws.save({**payload,'values':{'title':'different'}})
        item=first['item']
        with self.assertRaises(WorkspaceError):self.save(id=item['id'],version=1,status='已完成')
        for status in ('待执行','处理中','待复核'):
            item=self.save(id=item['id'],version=item['version'],status=status,note='处理记录')
        with self.assertRaises(WorkspaceError):self.save(id=item['id'],version=1,values={'title':'覆盖旧值'})
        with self.assertRaises(WorkspaceError):self.save(id=item['id'],version=item['version'],status='已完成')
        item=self.save(id=item['id'],version=item['version'],status='已完成',values={'result':'实际结果','evidence':'原始证据ID'})
        self.assertEqual(len(item['history']),5)
        with self.assertRaises(WorkspaceError):self.save(id=item['id'],version=item['version'],values={'result':'rewrite'})
        self.assertEqual(len(Workspace('demo',self.temp.name).listing({'kind':'workflow'})['rows']),1)
        self.assertEqual(Workspace('live',self.temp.name).listing({'kind':'workflow'})['rows'],[])

    def test_plans_reports_and_exact_sources(self):
        plan=self.save(kind='plan',values={'title':'生产计划'})
        with self.assertRaises(WorkspaceError):self.save(kind='workflow',values={'title':'执行','plan_id':'not-a-plan'})
        event=self.save(kind='workflow',values={'title':'执行','plan_id':plan['id'],'links':'production.采购订单表:原始ID'})
        self.assertEqual(event['values']['plan_id'],plan['id'])
        report=self.save(kind='report',values={'title':'十一月审计','start':'2026-11-01','due':'2026-11-30'})
        with self.assertRaises(WorkspaceError):self.save(id=report['id'],version=report['version'],status='已发布')
        report=self.save(id=report['id'],version=report['version'],status='已发布',values={'owner':'复核人','scope':'明确范围','conclusion':'仍有未核事项'})
        with self.assertRaises(WorkspaceError):self.save(id=report['id'],version=report['version'],values={'conclusion':'覆盖报告'})
        self.assertEqual(self.ws.listing({'kind':'report','start':'2026-12-01'})['rows'],[])
        self.assertEqual(len(self.ws.listing({'kind':'report','start':'2026-11-14','end':'2026-11-30'})['rows']),1)
        with self.assertRaises(WorkspaceError):self.ws.listing({'kind':'plan','start':'bad'})
        for key in ('../other','other'):
            with self.assertRaises(WorkspaceError):Workspace(key,self.temp.name)

    def test_annotation_ownership(self):
        for name in ('意见采纳表','意见执行表','整改处理表','履约提示表','合规自查表','整改跟踪表'):
            self.assertTrue(presentation('legal',name)['retired'])
        self.assertEqual(presentation('finance','资金用途核定表')['area'],'audit')
        self.assertEqual(presentation('legal','法规登记表')['area'],'archive')
        self.assertFalse(presentation('production','生产工时表')['standalone'])
        self.assertEqual(presentation('production','生产工单表')['area'],'workflow')
        self.assertEqual(presentation('production','库存盘点表')['label'],'库存盘点与余额')

    def test_invalid_payloads_have_readable_errors(self):
        for payload in ({'id':[]},{'kind':[]},{'kind':'workflow','values':{'title':Decimal('1.5')}},
                        {'kind':'workflow','values':{'title':'t'},'status':[]},
                        {'kind':'plan','values':{'title':'t','start':'20261114'}}):
            with self.assertRaises(WorkspaceError):self.save(**payload)

if __name__=='__main__': unittest.main(verbosity=2)
