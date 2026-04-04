"""
Scheduled Report Generator
============================
Command-line script for automated report generation via Windows Task Scheduler.

Usage:
    python scripts/scheduled_report.py --inp models/Net1.inp --output C:\\Reports --format docx
"""

import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description='Generate scheduled hydraulic report')
    parser.add_argument('--inp', required=True, help='Network .inp file path')
    parser.add_argument('--output', required=True, help='Output directory')
    parser.add_argument('--format', default='docx', choices=['docx', 'pdf', 'both'])
    parser.add_argument('--engineer', default='', help='Engineer name for report')
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(args.output, exist_ok=True)

    # Load and analyse
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()

    try:
        api.load_network_from_path(args.inp)
    except Exception as e:
        print(f"ERROR: Could not load {args.inp}: {e}")
        sys.exit(1)

    print(f"Loaded network: {os.path.basename(args.inp)}")

    results = api.run_steady_state(save_plot=False)
    print(f"Analysis complete: {len(results.get('pressures', {}))} junctions")

    # Build report data
    summary = api.get_network_summary()
    report_results = {'steady_state': results}

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    project_name = os.path.splitext(os.path.basename(args.inp))[0]

    # Generate reports
    if args.format in ('docx', 'both'):
        from reports.docx_report import generate_docx_report
        docx_path = os.path.join(args.output, f'{project_name}_{timestamp}.docx')
        generate_docx_report(
            report_results, summary, docx_path,
            engineer_name=args.engineer,
            project_name=project_name,
        )
        print(f"DOCX: {docx_path}")

    if args.format in ('pdf', 'both'):
        from reports.pdf_report import generate_pdf_report
        pdf_path = os.path.join(args.output, f'{project_name}_{timestamp}.pdf')
        generate_pdf_report(
            report_results, summary, pdf_path,
            engineer_name=args.engineer,
            project_name=project_name,
        )
        print(f"PDF: {pdf_path}")

    print("Done.")


if __name__ == '__main__':
    main()
