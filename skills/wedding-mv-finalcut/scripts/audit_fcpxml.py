#!/usr/bin/env python3
"""Read-only checks for flat Final Cut timelines and selected source ranges.

Only structural facts are checked. Smooth retimes and compound structures
require manual review; this helper never approves them by skipping them.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
import xml.etree.ElementTree as ET


class ManualReview(Exception):
    """The helper cannot prove this source range with its supported model."""


def seconds(value: str) -> Fraction:
    if not isinstance(value, str) or not value:
        raise ValueError('Missing or invalid FCPXML time value.')
    return Fraction(value[:-1] if value.endswith('s') else value)


def load_project(path: Path, name=None):
    entry = path/'Info.fcpxml' if path.is_dir() else path
    root = ET.parse(entry).getroot()
    if root.tag != 'fcpxml':
        raise ValueError('Input must be an FCPXML document.')
    resources = root.find('resources')
    if resources is None:
        raise ValueError('Missing FCPXML resources.')
    items = list(resources)
    ids = [item.get('id') for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate resource IDs.')
    projects = root.findall('.//project')
    if name is not None:
        projects = [p for p in projects if p.get('name') == name]
    if len(projects) != 1:
        raise ValueError('Choose exactly one project with --project / --selection-project.')
    sequence = projects[0].find('sequence')
    if sequence is None or sequence.find('spine') is None:
        raise ValueError('Project has no sequence/spine.')
    return projects[0], sequence, {item.get('id'): item for item in items}


def media_uri(asset):
    rep = asset.find("media-rep[@kind='original-media']")
    return rep.get('src', '') if rep is not None else ''


def source_key(asset):
    # Camera filenames can collide. Prefer the imported asset's identity.
    return ('uid', asset.get('uid')) if asset.get('uid') else ('uri', media_uri(asset))


def source_intervals(clip, asset):
    start = seconds(clip.get('start', asset.get('start', '0s')))
    end = start + seconds(clip.get('duration', '0s'))
    mapping = clip.find('timeMap')
    if mapping is None:
        return [(start, end)]
    pts = mapping.findall('timept')
    if len(pts) < 2 or any(p.get('interp', 'smooth2') != 'linear' for p in pts):
        raise ManualReview('平滑或不完整 timeMap 的源区间需要在 Final Cut 人工核对。')
    points = [(seconds(p.get('time')), seconds(p.get('value'))) for p in pts]
    if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError('timeMap point times must increase strictly.')

    def value_at(t):
        for (ta, va), (tb, vb) in zip(points, points[1:]):
            if ta <= t <= tb:
                return va + (vb-va)*(t-ta)/(tb-ta)
        raise ManualReview('片段超出 timeMap 已定义时钟，需人工核对。')

    # Include every internal point: a reverse or segmented retime can cross
    # an unselected hole even when its first and last source frames match.
    times = [start] + [t for t, _ in points if start < t < end] + [end]
    values = [value_at(t) for t in times]
    return [(min(a, b), max(a, b)) for a, b in zip(values, values[1:])]


def merged(intervals):
    result = []
    for a, b in sorted(intervals):
        if result and a <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], b))
        else:
            result.append((a, b))
    return result


def selection_ranges(sequence, resources):
    ranges, unresolved = {}, set()
    unsupported = {'ref-clip', 'mc-clip', 'sync-clip', 'clip', 'audition', 'transition'}
    if any(node.tag in unsupported for node in sequence.iter()):
        raise ManualReview('选材备份含复合 / 多机位 / 转场等结构，不能自动证明授权范围。')
    for clip in sequence.findall('.//asset-clip'):
        asset = resources.get(clip.get('ref'))
        if asset is None or asset.tag != 'asset':
            raise ValueError('Selection contains an unresolved asset reference.')
        if asset.get('hasVideo') != '1':
            continue  # Music is not the video selection boundary.
        key = source_key(asset)
        try:
            ranges.setdefault(key, []).extend(source_intervals(clip, asset))
        except ManualReview:
            unresolved.add(key)
    return {key: merged(value) for key, value in ranges.items()}, unresolved


def audit(path, project=None, expected_duration=None, selection=None,
          selection_project=None, check_media=True):
    selected, seq, resources = load_project(Path(path), project)
    report = {'project': selected.get('name'), 'media_existence_checked': check_media,
              'duration_seconds': float(seconds(seq.get('duration', '0s'))),
              'primary_asset_clips': 0, 'video_sources': [], 'errors': [], 'manual_review': []}
    errors, review = report['errors'], report['manual_review']

    def add(target, code, message, clip=None):
        item = {'code': code, 'message': message}
        if clip is not None:
            item['clip'] = clip.get('name', clip.tag)
        if item not in target:
            target.append(item)

    fmt = resources.get(seq.get('format'))
    if fmt is None or not fmt.get('frameDuration'):
        raise ValueError('Missing project frameDuration.')
    frame = seconds(fmt.get('frameDuration'))
    if frame <= 0:
        raise ValueError('Project frameDuration must be positive.')
    report['project_fps'] = str(1/frame)
    duration = seconds(seq.get('duration', '0s'))
    if expected_duration is not None and duration != seconds(str(expected_duration)):
        add(errors, 'duration_mismatch', '总长与本次要求不一致。')

    allowed, unresolved = None, set()
    if selection:
        _, before, before_resources = load_project(Path(selection), selection_project)
        try:
            allowed, unresolved = selection_ranges(before, before_resources)
        except ManualReview as exc:
            add(review, 'selection_complex', str(exc))

    cursor, primary_supported = Fraction(0), True
    spine = seq.find('spine')
    for clip in spine:
        if clip.tag not in {'asset-clip', 'gap'}:
            primary_supported = False
            add(review, 'primary_structure', '主故事线含非简单原片片段，需人工核对时序。', clip)
            continue
        offset = seconds(clip.get('offset', '0s'))
        length = seconds(clip.get('duration', '0s'))
        if primary_supported and offset != cursor:
            add(errors, 'gap_or_overlap', '主故事线有空隙或重叠。', clip)
        if offset/frame % 1 or length/frame % 1:
            add(errors, 'frame_boundary', '视频编辑点未落在工程帧边界。', clip)
        if length <= 0:
            add(errors, 'nonpositive_duration', '片段时长必须为正。', clip)
        if clip.tag == 'gap' and length > 0:
            add(errors, 'explicit_gap', '存在 gap；核对它是否为用户明确要求的留黑。', clip)
        if clip.tag == 'asset-clip':
            report['primary_asset_clips'] += 1
        cursor = offset + length
    if primary_supported and cursor != duration:
        add(errors, 'spine_duration', '主故事线结尾与声明总长不一致。')

    unsupported = {'ref-clip', 'mc-clip', 'sync-clip', 'clip', 'audition', 'transition'}
    if any(node.tag in unsupported for node in seq.iter()):
        add(review, 'nested_structure', '复合 / 多机位 / 转场等内容需应用内人工复核。')
    seen = set()
    for clip in seq.findall('.//asset-clip'):
        asset = resources.get(clip.get('ref'))
        if asset is None or asset.tag != 'asset':
            add(errors, 'missing_asset', '片段引用的 asset 不存在。', clip)
            continue
        uri = media_uri(asset)
        if not uri:
            add(errors, 'missing_original_reference', '没有原始媒体引用。', clip)
        elif check_media:
            parsed = urlparse(uri)
            if parsed.scheme == 'file' and parsed.netloc in {'', 'localhost'}:
                if not Path(unquote(parsed.path)).is_file():
                    add(errors, 'missing_media', '本机原始媒体文件不存在。', clip)
            else:
                add(review, 'nonlocal_media', '非本机 file URI，未验证媒体是否可用。', clip)
        if asset.get('hasVideo') != '1':
            continue
        key = source_key(asset)
        if key not in seen:
            report['video_sources'].append({'name': asset.get('name'),
                                           'uid': asset.get('uid'),
                                           'source_has_audio': asset.get('hasAudio') == '1'})
            seen.add(key)
        if allowed is not None and key not in allowed and key not in unresolved:
            add(errors, 'outside_selection_source', '加入了备份选材中没有的原片。', clip)
        if key in unresolved:
            add(review, 'selection_retime', '该原片的选材区间含复杂变速，需人工核对。', clip)
        try:
            intervals = source_intervals(clip, asset)
            asset_start = seconds(asset.get('start', '0s'))
            asset_end = asset_start + seconds(asset.get('duration', '0s'))
            if any(a < asset_start or b > asset_end for a, b in intervals):
                add(errors, 'outside_asset_duration', '片段使用的源时间超出原片长度。', clip)
            if allowed is not None and key in allowed and key not in unresolved:
                if any(not any(lo <= a and b <= hi for lo, hi in allowed[key])
                       for a, b in intervals):
                    add(errors, 'outside_selection_range', '使用了用户未选定的源区间。', clip)
        except ManualReview as exc:
            add(review, 'retime_requires_review', str(exc), clip)
    report['structural_status'] = 'errors' if errors else 'manual_review' if review else 'passed'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--project')
    parser.add_argument('--expected-duration', help='Exact seconds, e.g. 40 or 992/30.')
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--selection-project')
    parser.add_argument('--no-check-media', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = audit(args.input, args.project, args.expected_duration, args.selection,
                       args.selection_project, not args.no_check_media)
    except (OSError, ValueError, ET.ParseError, ZeroDivisionError, TypeError) as exc:
        print(json.dumps({'input_error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 3 if result['manual_review'] else 0


if __name__ == '__main__':
    sys.exit(main())
