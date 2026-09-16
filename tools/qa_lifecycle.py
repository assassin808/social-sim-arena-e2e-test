"""Isolated public-source season rehearsal; never imports refresh or model harness."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ssa.adapters import wikipedia
from ssa.ranking_round import rbo_loss

ROUND_IDS = ('wiki-top10-2026-09-06', 'wiki-top10-2026-09-27')
ENTRANT = 'qa-persistence-public-source'
END_AT = datetime(2026, 10, 1, tzinfo=timezone.utc)


class NotYetPublished(Exception):
    """Wikimedia has no list for a day that ended only hours ago.

    The daily top list appears some hours after the UTC day closes (at 01:12
    UTC on 2026-09-16 the 09-15 list was still 404), and the 00:43 run of the
    workflow asks for yesterday before it exists. That is not a broken source;
    the day is archived by a later run. `execute` treats it as "wait" while a
    round is still pending. At resolution time every target day must already be
    archived, so there it stays an error like any other."""


def stamp(now):
    return now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def get_day(day, output, now, fetch):
    """Immutable first-observed raw response, revalidated on every read."""
    if day >= now.date():
        raise ValueError('refusing current/future daily result')
    path = output / 'sources' / (day.isoformat() + '.json')
    if path.exists():
        saved = json.loads(path.read_text())
        raw = saved['raw_json'].encode()
        if digest(raw) != saved['sha256']:
            raise ValueError('archive hash mismatch: ' + str(day))
    else:
        url = wikipedia.top_url(day)
        raw = fetch(url)
        wikipedia.parse_top(json.loads(raw), day)
        saved = {'url': url, 'observed_day': str(day), 'fetched_at': stamp(now),
                 'sha256': digest(raw), 'raw_json': raw.decode()}
        write_json(path, saved)
    return wikipedia.parse_top(json.loads(raw), day), saved['sha256']


def week(end, output, now, fetch):
    totals, hashes = {}, {}
    for offset in range(6, -1, -1):
        day = end - timedelta(days=offset)
        articles, sha = get_day(day, output, now, fetch)
        hashes[str(day)] = sha
        for title, count in articles.items():
            totals[title] = totals.get(title, 0) + count
    return wikipedia.rank_totals(totals, 10), hashes


def execute(output, now, fetch, rounds=None):
    output = Path(output)
    rounds = rounds or json.loads((ROOT / 'questions/season0.json').read_text())['rounds']
    selected = [r for r in rounds if r['round_id'] in ROUND_IDS]
    if len(selected) != 2:
        raise ValueError('isolated two-round allowlist missing')
    rows = []
    for r in selected:
        rid = r['round_id']
        row = {'round_id': rid, 'question': r['question'], 'entrant': ENTRANT,
               'lock_at': r['lock_at'], 'release_at': r['release_at'],
               'mode': 'historical_replay' if rid == ROUND_IDS[0] else 'live_test',
               'status': 'pending', 'score': None}
        try:
            forecast_path = output / 'forecasts' / (rid + '.json')
            lock = datetime.fromisoformat(r['lock_at'].replace('Z', '+00:00'))
            if forecast_path.exists():
                forecast = json.loads(forecast_path.read_text())
                if forecast['round_id'] != rid or forecast['entrant'] != ENTRANT:
                    raise ValueError('forecast identity mismatch')
            else:
                if row['mode'] == 'live_test' and now >= lock:
                    row.update(status='missed_deadline', reason='no test forecast frozen before lock')
                    rows.append(row)
                    continue
                # Two weeks before target, fully published before its Friday lock.
                history_end = date.fromisoformat(r['ranking']['week_end']) - timedelta(days=14)
                ranking, hashes = week(history_end, output, now, fetch)
                forecast = {'round_id': rid, 'entrant': ENTRANT, 'ranking': ranking,
                            'filed_at': stamp(now), 'mode': row['mode'],
                            'history_week_end': str(history_end), 'source_hashes': hashes}
                write_json(forecast_path, forecast)
            row.update(filed_at=forecast['filed_at'], forecast=forecast['ranking'])
            if row['mode'] == 'live_test' and datetime.fromisoformat(forecast['filed_at'].replace('Z', '+00:00')) >= lock:
                raise ValueError('live forecast was filed after deadline')
            release = datetime.fromisoformat(r['release_at'].replace('Z', '+00:00'))
            if now < release:
                # Archive completed target days as they arrive, but never rank a partial week.
                target_start = date.fromisoformat(r['ranking']['week_start'])
                target_end = date.fromisoformat(r['ranking']['week_end'])
                row['target_days_archived'] = 0
                for offset in range(7):
                    day = target_start + timedelta(days=offset)
                    if day < now.date() and day <= target_end:
                        try:
                            get_day(day, output, now, fetch)
                        except NotYetPublished:
                            # Days are archived in order, so nothing after
                            # this one can exist yet either.
                            row['target_day_waiting'] = str(day)
                            break
                        row['target_days_archived'] += 1
                row['reason'] = 'real release time has not arrived; no outcome or score invented'
            else:
                resolution_path = output / 'resolutions' / (rid + '.json')
                if resolution_path.exists():
                    resolution = json.loads(resolution_path.read_text())
                else:
                    outcome, hashes = week(date.fromisoformat(r['ranking']['week_end']), output, now, fetch)
                    resolution = {'round_id': rid, 'resolved_at': stamp(now), 'outcome': outcome,
                                  'source_hashes': hashes, 'rule': r['resolve']}
                    write_json(resolution_path, resolution)
                row.update(status='resolved', outcome=resolution['outcome'],
                           resolved_at=resolution['resolved_at'],
                           score=rbo_loss(forecast['ranking'], resolution['outcome'], r['ranking']['rbo_p'], 10))
        except Exception as exc:
            row.update(status='blocked', reason=type(exc).__name__ + ': ' + str(exc)[:250])
        rows.append(row)
    report = {'generated_at': stamp(now), 'scope': 'isolated-test-only',
              'entrant': ENTRANT, 'paid_calls': 0, 'llm_calls': 0,
              'historical_replay_is_not_live_submission': True,
              'schedule_end_exclusive': stamp(END_AT), 'rounds': rows}
    write_json(output / 'report.json', report)
    body = ''.join('<tr><td>' + '</td><td>'.join(html.escape(str(x)) for x in
                   (r['round_id'], r['mode'], r['status'], r.get('filed_at', '—'),
                    r['score'] if r['score'] is not None else 'pending', r.get('reason', ''))) + '</td></tr>' for r in rows)
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Isolated lifecycle QA</title><style>body{font:16px system-ui;margin:2rem}td,th{padding:.6rem;border:1px solid #ddd}table{border-collapse:collapse}main{overflow:auto}</style><h1>Isolated lifecycle QA</h1><p>Real Wikimedia sources. Historical replay is not a contemporaneous submission. Future outcomes remain pending. No LLM calls.</p><p><a href="report.json">Machine-readable evidence</a></p><main><table><tr><th>Round</th><th>Mode</th><th>Status</th><th>Filed at</th><th>RBO loss (lower better)</th><th>Reason</th></tr>' + body + '</table></main>')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / 'qa-lifecycle'))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if now >= END_AT:
        print('Lifecycle window ended; no fetch or mutation.')
        return 0
    import requests
    def fetch(url):
        for attempt in range(3):
            time.sleep(1.2)
            response = requests.get(url, timeout=40, headers={'User-Agent': 'social-sim-arena-e2e-test/1.0 (QA; public Wikimedia data)'})
            if response.status_code == 429 and attempt < 2:
                retry = response.headers.get('Retry-After', '10')
                time.sleep(min(30, max(2, int(retry))) if retry.isdigit() else 10)
                continue
            if response.status_code == 404:
                raise NotYetPublished(url)
            response.raise_for_status()
            return response.content
    report = execute(args.output, now, fetch)
    for row in report['rounds']:
        print(row['round_id'], row['mode'], row['status'], row['score'])
    return int(any(r['status'] in ('blocked', 'missed_deadline') for r in report['rounds']))


if __name__ == '__main__':
    raise SystemExit(main())
