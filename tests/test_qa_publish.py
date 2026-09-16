import importlib.util,json,os,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
# A fixed clock inside the observation window: publish() refuses to write after
# 2026-10-01 UTC, and a test that read the real date went red on that day.
IN_WINDOW=datetime(2026,9,20,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('qa_publish',ROOT/'tools/publish_qa_results.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PublishQA(unittest.TestCase):
 def test_wrong_repository_is_rejected_before_network(self):
  with patch.dict(os.environ,{'GITHUB_REPOSITORY':'Social-Atoms/social-sim-arena'}),patch.object(m,'api') as api:
   with self.assertRaises(ValueError):m.publish('lifecycle',Path('.'))
   api.assert_not_called()
 def test_only_allowlisted_report_and_branch_are_written(self):
  calls=[]
  def api(path,method='GET',payload=None,optional=False):
   calls.append((path,method,payload))
   return {'sha':'blob'} if path=='git/blobs' else {'object':{'sha':'head'}} if path.startswith('git/ref/') else {'tree':{'sha':'tree'}} if path=='git/commits/head' else {'sha':'newtree'} if path=='git/trees' else {'sha':'commit'} if path=='git/commits' else {}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'qa-lifecycle').mkdir();(root/'qa-lifecycle/report.json').write_text('{"rounds":[]}')
   with patch.dict(os.environ,{'GITHUB_REPOSITORY':m.REPO,'GITHUB_RUN_ID':'123','GITHUB_SHA':'abc'}),patch.object(m,'api',side_effect=api):m.publish('lifecycle',root,now=IN_WINDOW)
  writes=[x for x in calls if x[1]=='PATCH'];self.assertEqual(writes,[('git/refs/heads/qa-results','PATCH',{'sha':'commit','force':False})])
  tree=next(x[2] for x in calls if x[0]=='git/trees');self.assertEqual(tree['base_tree'],'tree');self.assertEqual([e['path'] for e in tree['tree']],['qa-lifecycle/report.json'])
 def test_after_the_window_nothing_is_written(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'qa-lifecycle').mkdir();(root/'qa-lifecycle/report.json').write_text('{"rounds":[]}')
   with patch.dict(os.environ,{'GITHUB_REPOSITORY':m.REPO,'GITHUB_RUN_ID':'123','GITHUB_SHA':'abc'}),patch.object(m,'api') as api:
    m.publish('lifecycle',root,now=datetime(2026,10,1,tzinfo=timezone.utc))
    api.assert_not_called()
 def test_workflows_publish_failure_reports_without_main_push(self):
  for name in ['qa-lifecycle','qa-free-stability']:
   text=(ROOT/f'.github/workflows/{name}.yml').read_text();self.assertIn('needs:',text);self.assertIn('if: always()',text);self.assertNotIn('git push',text);self.assertIn('persist-credentials: false',text)
if __name__=='__main__':unittest.main()
