import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tools import qa_lifecycle as qa


class LifecycleTests(unittest.TestCase):
    def fake(self, url):
        y,m,d = url.split('/')[-3:]
        return json.dumps({'items':[{'year':y,'month':m,'day':d,'articles':[
            {'article':f'Article_{i}', 'views':100-i} for i in range(12)]}]}).encode()

    def test_live_pending_then_real_resolution_and_replay_cache(self):
        with tempfile.TemporaryDirectory() as td:
            calls=[]
            def fetch(url):
                calls.append(url)
                return self.fake(url)
            first=qa.execute(td,datetime(2026,9,15,tzinfo=timezone.utc),fetch)
            self.assertEqual([r['status'] for r in first['rounds']],['resolved','pending'])
            self.assertEqual(first['rounds'][0]['score'],0)
            self.assertIsNone(first['rounds'][1]['score'])
            self.assertEqual(len(calls),21)
            again=qa.execute(td,datetime(2026,9,16,tzinfo=timezone.utc),fetch)
            self.assertEqual(len(calls),21)
            self.assertEqual(first['rounds'][1]['filed_at'],again['rounds'][1]['filed_at'])
            final=qa.execute(td,datetime(2026,9,29,15,tzinfo=timezone.utc),fetch)
            self.assertEqual(final['rounds'][1]['status'],'resolved')
            self.assertEqual(len(calls),28)

    def test_yesterday_not_yet_published_is_waiting_not_blocked(self):
        # The 00:43 UTC run asks for yesterday before Wikimedia has produced
        # it. While the round is pending that is a wait, not a failure: the
        # forecast is untouched, the earlier days stay archived, and the next
        # run picks the day up.
        with tempfile.TemporaryDirectory() as td:
            qa.execute(td,datetime(2026,9,15,tzinfo=timezone.utc),self.fake)
            def lagging(url):
                if url.endswith('/2026/09/23'):
                    raise qa.NotYetPublished(url)
                return self.fake(url)
            report=qa.execute(td,datetime(2026,9,24,0,43,tzinfo=timezone.utc),lagging)
            live=report['rounds'][1]
            self.assertEqual(live['status'],'pending')
            self.assertEqual(live['target_days_archived'],2)
            self.assertEqual(live['target_day_waiting'],'2026-09-23')
            self.assertTrue((Path(td)/'sources/2026-09-22.json').exists())
            self.assertFalse((Path(td)/'sources/2026-09-23.json').exists())
            later=qa.execute(td,datetime(2026,9,24,6,43,tzinfo=timezone.utc),self.fake)
            self.assertEqual(later['rounds'][1]['target_days_archived'],3)
            self.assertNotIn('target_day_waiting',later['rounds'][1])
            # At resolution every target day must exist; a missing one is
            # still a blocked round, never an invented outcome.
            final=qa.execute(td,datetime(2026,9,29,15,tzinfo=timezone.utc),lagging)
            self.assertEqual(final['rounds'][1]['status'],'resolved')
            def gone(url):
                raise qa.NotYetPublished(url)
            with tempfile.TemporaryDirectory() as fresh:
                qa.execute(fresh,datetime(2026,9,15,tzinfo=timezone.utc),self.fake)
                blocked=qa.execute(fresh,datetime(2026,9,29,15,tzinfo=timezone.utc),gone)
                self.assertEqual(blocked['rounds'][1]['status'],'blocked')
                self.assertIn('NotYetPublished',blocked['rounds'][1]['reason'])

    def test_missed_deadline_cannot_be_backdated(self):
        with tempfile.TemporaryDirectory() as td:
            report=qa.execute(td,datetime(2026,9,20,tzinfo=timezone.utc),self.fake)
            self.assertEqual(report['rounds'][1]['status'],'missed_deadline')
            self.assertFalse((Path(td)/'forecasts'/f'{qa.ROUND_IDS[1]}.json').exists())

    def test_partial_or_wrong_date_does_not_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            def wrong(url):
                value=json.loads(self.fake(url));value['items'][0]['year']='2001'
                return json.dumps(value).encode()
            report=qa.execute(td,datetime(2026,9,15,tzinfo=timezone.utc),wrong)
            self.assertTrue(all(r['status']=='blocked' for r in report['rounds']))
            self.assertFalse((Path(td)/'resolutions').exists())

    def test_archive_tampering_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            qa.execute(td,datetime(2026,9,15,tzinfo=timezone.utc),self.fake)
            archive=next((Path(td)/'sources').glob('*.json'))
            data=json.loads(archive.read_text());data['sha256']='0'*64;archive.write_text(json.dumps(data))
            day=qa.date.fromisoformat(archive.stem)
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                qa.get_day(day,Path(td),datetime(2026,9,15,tzinfo=timezone.utc),self.fake)

if __name__=='__main__':unittest.main()
