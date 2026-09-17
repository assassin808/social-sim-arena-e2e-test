"""Isolated signed-intake clock/reveal/scoring rehearsal. Never runs refresh."""
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ssa import forecast_reveal, signed_forecasts as wire, scoring

def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'assassin808/social-sim-arena-e2e-test':
        raise RuntimeError('test fork only')
    if os.environ.get('GITHUB_REF_NAME') != 'qa-signed-intake-registry':
        raise RuntimeError('test registry branch only')
    spec=json.loads((ROOT/'qa/signed-lifecycle-trigger.json').read_text())
    rid=spec['round_id']; entrant=spec['entrant']; due=wire.utc(spec['lock_at'])
    if not rid.startswith('qa-signed-clock-') or entrant!='qa-signed-rehearsal':
        raise RuntimeError('unexpected test fixture')
    remaining=(due-datetime.now(timezone.utc)).total_seconds()
    if remaining>600: raise RuntimeError('test deadline too distant')
    while datetime.now(timezone.utc)<=due:
        time.sleep(min(10,max(0.1,(due-datetime.now(timezone.utc)).total_seconds()+0.2)))
    subprocess.run(['git','fetch','origin','sealed:refs/remotes/origin/sealed'],cwd=ROOT,check=True)
    forecast_reveal.reveal(ROOT,'refs/remotes/origin/sealed',json.loads(os.environ['SSA_AGE_IDENTITIES']))
    forecast=json.loads((ROOT/f'forecasts/{rid}/{entrant}.json').read_text())
    assert forecast['topline']['mean']==spec['expected_final_mean'], 'did not reveal the final valid version'
    proof=json.loads((ROOT/f'reveal-receipts/{rid}/{entrant}.json').read_text())
    source=forecast_reveal.document(ROOT,proof['source_commit'],proof['source_path'])
    score=scoring.crps_forecast(forecast['topline'],spec['synthetic_outcome'])
    report={'mode':'synthetic-clock-rehearsal','status':'passed','generated_at':wire.stamp(datetime.now(timezone.utc)),
        'round_id':rid,'entrant':entrant,'lock_at':spec['lock_at'],'received_at':source['received_at'],
        'revealed_forecast':forecast['topline'],'synthetic_outcome':spec['synthetic_outcome'],'crps':score,
        'source_commit':proof['source_commit'],'ciphertext_sha256':proof['ciphertext_sha256'],
        'run_url':f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        'note':'Real wall-clock deadline, GitHub storage and Actions reveal; controlled synthetic outcome, no paid model or real-season settlement.'}
    target=ROOT/'qa-signed-lifecycle/report.json';target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n')
    print('Deadline passed; final signed forecast revealed and scored.')
if __name__=='__main__':main()
