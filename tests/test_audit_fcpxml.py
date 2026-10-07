"""Synthetic timelines only: no client footage, paths, or native bookmarks."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as E

MODULE_PATH = Path(__file__).resolve().parents[1]/'skills/wedding-mv-finalcut/scripts/audit_fcpxml.py'
spec = importlib.util.spec_from_file_location('audit_fcpxml', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TimelineAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.media = self.folder/'synthetic camera file.mp4'
        self.media.touch()  # Only filesystem existence is in the helper's scope.

    def write(self, filename, clips, duration='2s', uid='SYNTHETIC-A', frame='1/30s', mapping=None):
        root = E.Element('fcpxml', version='1.14')
        res = E.SubElement(root, 'resources')
        E.SubElement(res, 'format', id='fmt', frameDuration=frame)
        asset = E.SubElement(res, 'asset', id='a', name='CAMERA001', uid=uid,
                             start='0s', duration='10s', hasVideo='1', hasAudio='1')
        E.SubElement(asset, 'media-rep', kind='original-media', src=self.media.as_uri())
        project = E.SubElement(root, 'project', name='Synthetic')
        sequence = E.SubElement(project, 'sequence', format='fmt', duration=duration)
        spine = E.SubElement(sequence, 'spine')
        for attrs in clips:
            node = E.SubElement(spine, 'asset-clip', ref='a', name='CAMERA001', **attrs)
            if mapping:
                tm = E.SubElement(node, 'timeMap')
                for t, value, interp in mapping:
                    E.SubElement(tm, 'timept', time=t, value=value, interp=interp)
        path = self.folder/filename
        E.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
        return path

    @staticmethod
    def codes(report):
        return {e['code'] for e in report['errors']}

    def test_contiguous_original_clips_and_encoded_file_url(self):
        path = self.write('valid.fcpxml', [dict(offset='0s', start='1s', duration='1s'),
                                          dict(offset='1s', start='3s', duration='1s')])
        report = module.audit(path, expected_duration='2')
        self.assertEqual(report['structural_status'], 'passed')
        self.assertTrue(report['video_sources'][0]['source_has_audio'])

    def test_missing_original_media(self):
        path = self.write('missing.fcpxml', [dict(offset='0s', duration='2s')])
        self.media.unlink()
        self.assertIn('missing_media', self.codes(module.audit(path)))

    def test_gap_overlap_frame_boundary_and_wrong_target_length(self):
        path = self.write('gap.fcpxml', [dict(offset='0s', duration='1s'),
                                        dict(offset='31/30s', duration='29/30s')])
        self.assertIn('gap_or_overlap', self.codes(module.audit(path)))
        path = self.write('overlap.fcpxml', [dict(offset='0s', duration='1s'),
                                            dict(offset='29/30s', duration='31/30s')])
        self.assertIn('gap_or_overlap', self.codes(module.audit(path)))
        path = self.write('partial.fcpxml', [dict(offset='0s', duration='1/60s')], '1/60s')
        self.assertIn('frame_boundary', self.codes(module.audit(path)))
        self.assertIn('duration_mismatch', self.codes(module.audit(path, expected_duration='40')))

    def test_selection_limits_source_in_and_source_identity(self):
        before = self.write('before.fcpxml', [dict(offset='0s', start='2s', duration='2s')])
        good = self.write('good.fcpxml', [dict(offset='0s', start='5/2s', duration='1s')], '1s')
        self.assertEqual(module.audit(good, selection=before)['structural_status'], 'passed')
        early = self.write('early.fcpxml', [dict(offset='0s', start='3/2s', duration='1s')], '1s')
        self.assertIn('outside_selection_range', self.codes(module.audit(early, selection=before)))
        same_name = self.write('different-camera.fcpxml', [dict(offset='0s', start='2s', duration='1s')],
                               '1s', uid='SYNTHETIC-B')
        self.assertIn('outside_selection_source', self.codes(module.audit(same_name, selection=before)))

    def test_unselected_hole_is_not_implicitly_authorized(self):
        before = self.write('holes.fcpxml', [dict(offset='0s', start='1s', duration='1s'),
                                            dict(offset='1s', start='4s', duration='1s')])
        after = self.write('crossing.fcpxml', [dict(offset='0s', start='1s', duration='4s')], '4s')
        self.assertIn('outside_selection_range', self.codes(module.audit(after, selection=before)))

    def test_linear_retime_uses_adjusted_local_clock(self):
        before = self.write('before.fcpxml', [dict(offset='0s', start='2s', duration='2s')])
        after = self.write('slow.fcpxml', [dict(offset='0s', start='4s', duration='2s')],
                           mapping=[('0s', '0s', 'linear'), ('20s', '10s', 'linear')])
        self.assertEqual(module.audit(after, selection=before)['structural_status'], 'passed')

    def test_reverse_midpoint_cannot_hide_an_excursion(self):
        before = self.write('before.fcpxml', [dict(offset='0s', start='1s', duration='2s')])
        after = self.write('reverse.fcpxml', [dict(offset='0s', start='0s', duration='2s')],
                           mapping=[('0s', '1s', 'linear'), ('1s', '5s', 'linear'),
                                    ('2s', '1s', 'linear')])
        self.assertIn('outside_selection_range', self.codes(module.audit(after, selection=before)))

    def test_smooth_retime_requires_manual_review(self):
        after = self.write('smooth.fcpxml', [dict(offset='0s', duration='2s')],
                           mapping=[('0s', '0s', 'smooth2'), ('2s', '3s', 'smooth2')])
        report = module.audit(after)
        self.assertEqual(report['structural_status'], 'manual_review')
        self.assertFalse(report['errors'])

    def test_noninteger_project_fps_uses_exact_fractions(self):
        path = self.write('ntsc.fcpxml', [dict(offset='0s', duration='1001/1000s')],
                          duration='1001/1000s', frame='1001/30000s')
        self.assertEqual(module.audit(path)['structural_status'], 'passed')

    def test_compound_structure_is_not_silently_approved(self):
        path = self.write('compound.fcpxml', [dict(offset='0s', duration='2s')])
        tree = E.parse(path)
        tree.find('.//spine')[0].tag = 'ref-clip'
        tree.write(path)
        self.assertEqual(module.audit(path)['structural_status'], 'manual_review')

    def test_fcpxmld_and_ambiguous_project(self):
        path = self.write('one.fcpxml', [dict(offset='0s', duration='2s')])
        bundle = self.folder/'test.fcpxmld'
        bundle.mkdir()
        (bundle/'Info.fcpxml').write_bytes(path.read_bytes())
        self.assertEqual(module.audit(bundle)['structural_status'], 'passed')
        tree = E.parse(path)
        E.SubElement(tree.getroot(), 'project', name='Other')
        tree.write(path)
        with self.assertRaises(ValueError):
            module.audit(path)
        self.assertEqual(module.audit(path, project='Synthetic')['structural_status'], 'passed')


if __name__ == '__main__':
    unittest.main()
