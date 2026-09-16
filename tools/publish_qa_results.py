"""Publish only allowlisted public QA JSON to the isolated qa-results branch."""
import argparse,base64,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
REPO='assassin808/social-sim-arena-e2e-test'
BRANCH='qa-results'
PATHS={'lifecycle':'qa-lifecycle/report.json','stability':'qa-stability/latest.json'}
def api(path,method='GET',payload=None,optional=False):
 args=['gh','api',f'repos/{REPO}/'+path,'--method',method]
 if payload is not None:args+=['--input','-']
 r=subprocess.run(args,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True)
 if r.returncode:
  if optional and '404' in r.stderr:return None
  raise RuntimeError('GitHub publication failed: '+r.stderr[:250])
 return json.loads(r.stdout) if r.stdout else None

def publish(channel,root,now=None):
 if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise ValueError('Only the isolated test repository is allowed')
 now=now or datetime.now(timezone.utc)
 if now>=datetime(2026,10,1,tzinfo=timezone.utc):
  print('Observation window ended; publication skipped');return
 path=PATHS[channel];raw=(root/path).read_bytes()
 if len(raw)>1_000_000:raise ValueError('Oversized report')
 data=json.loads(raw);required='rounds' if channel=='lifecycle' else 'models'
 if not isinstance(data.get(required),list):raise ValueError('Invalid report schema')
 data['_publication']={'published_at':now.isoformat(),'run_url':f"https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}",'source_commit':os.environ['GITHUB_SHA']}
 blob=api('git/blobs','POST',{'content':json.dumps(data,ensure_ascii=False,indent=2)+'\n','encoding':'utf-8'})['sha']
 for attempt in range(3):
  ref=api('git/ref/heads/'+BRANCH,optional=True);parent=ref['object']['sha'] if ref else None
  tree={'tree':[{'path':path,'mode':'100644','type':'blob','sha':blob}]}
  if parent:tree['base_tree']=api('git/commits/'+parent)['tree']['sha']
  tree_sha=api('git/trees','POST',tree)['sha']
  commit=api('git/commits','POST',{'message':f'Publish isolated {channel} QA result','tree':tree_sha,'parents':[parent] if parent else []})['sha']
  try:
   if parent:api('git/refs/heads/'+BRANCH,'PATCH',{'sha':commit,'force':False})
   else:api('git/refs','POST',{'ref':'refs/heads/'+BRANCH,'sha':commit})
   print('Published',path,'to',BRANCH,commit);return
  except RuntimeError:
   if attempt==2:raise
   time.sleep(1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('channel',choices=PATHS);p.add_argument('--root',type=Path,default=Path('.'));a=p.parse_args();publish(a.channel,a.root)
