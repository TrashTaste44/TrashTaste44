import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fetch_stats', ROOT / 'scripts/fetch_stats.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class FetchTests(unittest.TestCase):
    def test_calendar_uses_counts_not_color_levels_and_handles_shuffled_tooltips(self):
        parser = fetch.CalendarParser()
        parser.feed('''<td id="a" data-date="2026-10-25" data-level="4"></td>
          <td id="b" data-date="2026-10-26" data-level="0"></td>
          <tool-tip for="b">No contributions on October 26th.</tool-tip>
          <tool-tip for="a">1,234 contributions on October 25th.</tool-tip>''')
        self.assertEqual(parser.days(), {'2026-10-25': 1234, '2026-10-26': 0})

    def test_missing_calendar_counts_fail_instead_of_becoming_fake_zeros(self):
        with patch.object(fetch, 'request', return_value='<html>Unavailable</html>'):
            with self.assertRaisesRegex(RuntimeError, 'all 30'):
                fetch.collect('TrashTaste44', date(2026, 10, 26), True)

    def test_api_paginates_and_aggregates_language_bytes(self):
        def page(size, more, cursor):
            return json.dumps({'data': {'user': {
                'contributionsCollection': {'contributionCalendar': {'weeks': [{
                    'contributionDays': [{'date': '2026-10-26', 'contributionCount': 7}]
                }]}},
                'repositories': {'pageInfo': {'hasNextPage': more, 'endCursor': cursor},
                    'nodes': [{'languages': {'pageInfo': {'hasNextPage': False},
                        'edges': [{'size': size, 'node': {'name': 'Python'}}]}}]}
            }}})
        with patch.object(fetch, 'request', side_effect=[page(30, True, 'next'), page(70, False, 'end')]) as request:
            days, languages = fetch.api_stats('TrashTaste44', date(2026, 9, 27), date(2026, 10, 26), 'test-token')
        self.assertEqual(languages, {'Python': 100})
        self.assertEqual(days, {'2026-10-26': 7})
        self.assertEqual(request.call_args_list[1].args[1]['variables']['cursor'], 'next')
        self.assertIn('privacy: PUBLIC', fetch.QUERY)
        self.assertIn('isFork: false', fetch.QUERY)

    def test_api_errors_do_not_emit_partial_data(self):
        with patch.object(fetch, 'request', return_value=json.dumps({'errors': [{'message': 'denied'}]})):
            with self.assertRaisesRegex(RuntimeError, 'complete profile stats'):
                fetch.api_stats('TrashTaste44', date(2026, 9, 27), date(2026, 10, 26), 'test-token')


class AnimationTests(unittest.TestCase):
    def render(self, folder, languages, count=0):
        stats = {
            'username': 'TrashTaste44', 'updated_at': '2026-10-26T00:00:00+00:00',
            'source': 'unit-test fixture', 'language_status': 'complete',
            'language_scope': 'Public owned non-fork repositories',
            'contributions': [{'date': (date(2026, 9, 27) + timedelta(days=i)).isoformat(),
                               'count': count} for i in range(30)],
            'languages': languages,
        }
        path = folder / 'stats.json'
        path.write_text(json.dumps(stats))
        subprocess.run([sys.executable, str(ROOT / 'scripts/render_profile.py'),
                        '--stats', str(path), '--output-dir', str(folder)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_zero_activity_renders_and_snake_never_crosses_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.render(folder, [])
            with Image.open(folder / 'profile.gif') as gif:
                self.assertGreater(gif.n_frames, 300)
                self.assertEqual(gif.info['loop'], 0)
                # Includes heading text, descenders, and its surrounding whitespace.
                regions = [(30, 288, 430, 327), (30, 590, 430, 632)]
                expected = [gif.convert('RGB').crop(region).tobytes() for region in regions]
                for index in range(gif.n_frames):
                    gif.seek(index)
                    for region, pixels in zip(regions, expected):
                        self.assertEqual(gif.convert('RGB').crop(region).tobytes(), pixels,
                                         f'Snake overlaps heading in frame {index}')
            summary = (folder / 'profile-summary.md').read_text()
            self.assertIn('no language bytes', summary)
            self.assertNotIn('session active', summary)

    def test_multiple_languages_fit_and_percentages_use_all_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.render(folder, [{'name': f'Language{i}', 'bytes': 100} for i in range(7)], count=1200)
            with Image.open(folder / 'profile.png') as image:
                self.assertEqual(image.height, 945)
            summary = (folder / 'profile-summary.md').read_text()
            self.assertEqual(summary.count('14.3%'), 7)
            self.assertIn('1200', summary)


if __name__ == '__main__':
    unittest.main()
