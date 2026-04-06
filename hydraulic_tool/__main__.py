"""
Hydraulic Tool CLI — Headless Analysis
=======================================
Usage:
    python -m hydraulic_tool analyse network.inp --format json
    python -m hydraulic_tool analyse network.inp --format csv
    python -m hydraulic_tool report  network.inp --output report.docx
    python -m hydraulic_tool validate network.inp

No GUI dependencies required — runs entirely headless.
"""

import argparse
import csv
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_api(inp_path):
    """Load network and return HydraulicAPI instance."""
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.load_network(inp_path)
    return api


def cmd_analyse(args):
    """Run steady-state analysis and output results."""
    api = _load_api(args.inp)
    results = api.run_steady_state(save_plot=False)

    if 'error' in results:
        print(f"Error: {results['error']}", file=sys.stderr)
        return 1

    if args.format == 'json':
        # JSON output — serialise results dict
        print(json.dumps(results, indent=2, default=str))
    elif args.format == 'csv':
        # CSV output — node pressures + pipe flows
        writer = csv.writer(sys.stdout)

        writer.writerow(['# Node Pressures'])
        writer.writerow(['Junction', 'Min (m)', 'Max (m)', 'Avg (m)'])
        for jid, p in results.get('pressures', {}).items():
            writer.writerow([jid, p.get('min_m', ''), p.get('max_m', ''),
                             p.get('avg_m', '')])

        writer.writerow([])
        writer.writerow(['# Pipe Flows'])
        writer.writerow(['Pipe', 'Avg (LPS)', 'Velocity (m/s)',
                         'Headloss (m/km)'])
        for pid, f in results.get('flows', {}).items():
            writer.writerow([pid, f.get('avg_lps', ''),
                             f.get('max_velocity_ms', ''),
                             f.get('headloss_per_km', '')])

        # Compliance
        compliance = results.get('compliance', [])
        if compliance:
            writer.writerow([])
            writer.writerow(['# Compliance'])
            writer.writerow(['Type', 'Element', 'Message'])
            for c in compliance:
                writer.writerow([c.get('type', ''), c.get('element', ''),
                                 c.get('message', '')])
    return 0


def cmd_report(args):
    """Generate DOCX report."""
    api = _load_api(args.inp)
    results = api.run_steady_state(save_plot=False)

    if 'error' in results:
        print(f"Error: {results['error']}", file=sys.stderr)
        return 1

    from reports.docx_report import generate_docx_report
    summary = api.get_network_summary()
    output = args.output or os.path.splitext(args.inp)[0] + '_report.docx'
    generate_docx_report(
        {'steady_state': results}, summary, output,
        project_name=os.path.basename(args.inp).replace('.inp', ''))
    print(f"Report generated: {output}")
    return 0


def cmd_validate(args):
    """Validate network and print compliance results."""
    api = _load_api(args.inp)
    results = api.run_steady_state(save_plot=False)

    if 'error' in results:
        print(f"Error: {results['error']}", file=sys.stderr)
        return 1

    compliance = results.get('compliance', [])
    warnings = [c for c in compliance if c.get('type') in ('WARNING', 'CRITICAL')]
    infos = [c for c in compliance if c.get('type') == 'INFO']

    if not warnings:
        print(f"PASS — {len(compliance)} checks, 0 issues")
    else:
        print(f"FAIL — {len(warnings)} issue(s):")
        for c in warnings:
            print(f"  [{c['type']}] {c.get('element', '')}: {c.get('message', '')}")

    if infos:
        print(f"\n{len(infos)} informational item(s):")
        for c in infos:
            print(f"  [INFO] {c.get('element', '')}: {c.get('message', '')}")

    return 1 if warnings else 0


def main():
    parser = argparse.ArgumentParser(
        prog='hydraulic_tool',
        description='EPANET Hydraulic Analysis Toolkit — CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # analyse
    p_analyse = subparsers.add_parser('analyse', help='Run steady-state analysis')
    p_analyse.add_argument('inp', help='Path to .inp network file')
    p_analyse.add_argument('--format', choices=['json', 'csv'], default='json',
                           help='Output format (default: json)')

    # report
    p_report = subparsers.add_parser('report', help='Generate DOCX report')
    p_report.add_argument('inp', help='Path to .inp network file')
    p_report.add_argument('--output', '-o', help='Output .docx path')

    # validate
    p_validate = subparsers.add_parser('validate', help='Validate network compliance')
    p_validate.add_argument('inp', help='Path to .inp network file')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    handlers = {
        'analyse': cmd_analyse,
        'report': cmd_report,
        'validate': cmd_validate,
    }
    return handlers[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
