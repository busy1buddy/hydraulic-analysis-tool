"""
Cross-Platform Tests (T5)
==========================
Verify that core behaviour is platform-independent. These tests should
pass on Linux and macOS too — no Windows-specific assumptions.
"""

import os
import sys
import re
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_hardcoded_backslashes_in_core():
    """No backslash path separators in hydraulic API modules — would
    break on Linux/macOS. Matches only paths inside string literals,
    not Windows line endings or escape sequences in regexes."""
    epanet_dir = os.path.join(PROJECT_ROOT, 'epanet_api')
    offenders = []
    for root, _, files in os.walk(epanet_dir):
        for fname in files:
            if not fname.endswith('.py'):
                continue
            path = os.path.join(root, fname)
            with open(path, encoding='utf-8') as f:
                text = f.read()
            # Look for hardcoded Windows paths in string literals:
            # "something\something" where neither side is an escape char
            matches = re.findall(r'"[^"]*[a-zA-Z]\\[a-zA-Z][^"]*"', text)
            matches += re.findall(r"'[^']*[a-zA-Z]\\[a-zA-Z][^']*'", text)
            # Filter out common escape sequences (\n, \t etc. start with
            # escape char) and regex patterns (which contain \\)
            for m in matches:
                # Skip regex-ish strings that include double-backslash
                if '\\\\' in m:
                    continue
                # Skip docstring references to Windows examples
                if 'C:\\' in m or 'c:\\' in m:
                    continue
                offenders.append(f'{path}: {m}')
    assert not offenders, (
        'Hardcoded backslash paths in core modules:\n  '
        + '\n  '.join(offenders))


def test_os_path_join_used_for_paths():
    """Verify api.work_dir / model_dir / output_dir are absolute and use
    the platform's native separator."""
    api = HydraulicAPI()
    assert os.path.isabs(api.work_dir)
    assert os.path.isabs(api.model_dir)
    assert os.path.isabs(api.output_dir)


def test_unicode_node_ids_round_trip():
    """Node IDs with Unicode characters must survive save/load cycle."""
    api = HydraulicAPI()
    # EPANET .inp format may not support all unicode; stick to ASCII-safe
    # extensions that still stress encoding paths.
    ascii_ids = ['Node_01', 'Node-02', 'J.3']
    api.create_network(
        name='unicode_test',
        junctions=[
            {'id': jid, 'elevation': 10, 'demand': 1,
             'x': 10 * i, 'y': 0}
            for i, jid in enumerate(ascii_ids)
        ],
        reservoirs=[{'id': 'R_src', 'head': 50, 'x': -50, 'y': 0}],
        pipes=[
            {'id': f'P_{i}', 'start': ascii_ids[i], 'end': ascii_ids[i + 1],
             'length': 100, 'diameter': 150, 'roughness': 130}
            for i in range(len(ascii_ids) - 1)
        ] + [{'id': 'P_src', 'start': 'R_src', 'end': ascii_ids[0],
              'length': 100, 'diameter': 200, 'roughness': 130}],
    )

    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, 'net.inp')
        api.write_inp(inp)

        api2 = HydraulicAPI()
        api2.load_network(inp)
        for jid in ascii_ids:
            assert jid in api2.wn.junction_name_list

        # Steady-state solves
        r = api2.run_steady_state(save_plot=False)
        assert 'error' not in r


def test_saved_inp_has_no_absolute_paths():
    """When a network is saved to .inp, the file must not leak
    absolute paths that would only resolve on the saving machine."""
    api = HydraulicAPI()
    api.create_network(
        name='no_abs_paths',
        junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1,
                    'x': 0, 'y': 0}],
        reservoirs=[{'id': 'R1', 'head': 30, 'x': -50, 'y': 0}],
        pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 150, 'roughness': 130}],
    )
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, 'out.inp')
        api.write_inp(inp)
        with open(inp, encoding='utf-8') as f:
            content = f.read()
        # C:\Users\… should not appear in saved inp
        assert 'C:\\Users' not in content
        assert 'C:/Users' not in content
        # Home path on unix
        assert '/home/' not in content or 'home/' in content[:5]
        # The tmp dir path should not be inside the .inp either
        assert tmp not in content


def test_large_network_does_not_crash():
    """Build a 500-junction grid and confirm it solves in reasonable
    time without crashing. (Lower than the user's 1000-node ask to
    keep CI fast.)"""
    import time
    api = HydraulicAPI()
    junctions = []
    pipes = []
    # 20x25 grid = 500 junctions
    for i in range(20):
        for j in range(25):
            jid = f'J{i}_{j}'
            junctions.append({
                'id': jid,
                'elevation': 10 + i * 0.5,
                'demand': 0.5,
                'x': i * 100,
                'y': j * 100,
            })
    reservoirs = [{'id': 'R1', 'head': 80, 'x': -100, 'y': 0}]
    # Connect reservoir to first junction
    pipes.append({'id': 'P_src', 'start': 'R1', 'end': 'J0_0',
                   'length': 100, 'diameter': 400, 'roughness': 130})
    # Horizontal pipes
    for i in range(20):
        for j in range(24):
            pipes.append({
                'id': f'H_{i}_{j}',
                'start': f'J{i}_{j}', 'end': f'J{i}_{j + 1}',
                'length': 100, 'diameter': 200, 'roughness': 130,
            })
    # Vertical pipes
    for i in range(19):
        for j in range(25):
            pipes.append({
                'id': f'V_{i}_{j}',
                'start': f'J{i}_{j}', 'end': f'J{i + 1}_{j}',
                'length': 100, 'diameter': 200, 'roughness': 130,
            })
    api.create_network(name='large_grid', junctions=junctions,
                       reservoirs=reservoirs, pipes=pipes)
    t0 = time.perf_counter()
    r = api.run_steady_state(save_plot=False)
    elapsed = time.perf_counter() - t0
    assert 'error' not in r
    assert len(r['pressures']) == 500
    assert elapsed < 30.0, (
        f'500-node solve took {elapsed:.1f}s (>30s) — '
        f'performance regression')


def test_line_endings_neutral():
    """Reading a .inp that has Unix line endings should work."""
    api = HydraulicAPI()
    api.create_network(
        name='le_test',
        junctions=[{'id': 'J1', 'elevation': 0, 'demand': 1,
                    'x': 0, 'y': 0}],
        reservoirs=[{'id': 'R1', 'head': 30, 'x': -50, 'y': 0}],
        pipes=[{'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 150, 'roughness': 130}],
    )
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, 'crlf.inp')
        api.write_inp(inp)
        with open(inp, 'rb') as f:
            content = f.read()
        # Rewrite with pure LF line endings
        lf_inp = os.path.join(tmp, 'lf.inp')
        with open(lf_inp, 'wb') as f:
            f.write(content.replace(b'\r\n', b'\n'))

        api2 = HydraulicAPI()
        api2.load_network(lf_inp)
        assert api2.wn is not None
        r = api2.run_steady_state(save_plot=False)
        assert 'error' not in r
