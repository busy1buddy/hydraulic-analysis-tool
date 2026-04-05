"""
PDF Report Generator for EPANET Hydraulic Analysis
====================================================
Uses fpdf2 to produce a PDF. If fpdf2 is unavailable, falls back to
generating an HTML file that can be opened in a browser and printed to PDF.
"""

from datetime import date
import os

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False


# Helvetica is a Latin-1 font and cannot render unicode glyphs like m², °,
# μ, ≤, ≥, en/em-dashes that appear throughout the engineering data
# (slurry rheology, WSAA labels, statistics). Sanitize every string we
# write so the user never sees "Character X outside range of Helvetica".
_UNICODE_MAP = {
    '\u00b2': '^2',    # ²  (m², mm²)
    '\u00b3': '^3',    # ³  (m³)
    '\u00b0': ' deg',  # °
    '\u00b5': 'u',     # µ (micro sign)
    '\u03bc': 'u',     # μ (Greek mu)
    '\u2264': '<=',    # ≤
    '\u2265': '>=',    # ≥
    '\u2013': '-',     # en-dash
    '\u2014': '--',    # em-dash
    '\u2022': '*',     # bullet
    '\u00b1': '+/-',   # ±
    '\u00d7': 'x',     # ×
    '\u2192': '->',    # →
    '\u2190': '<-',    # ←
    '\u2026': '...',   # ellipsis
    '\u00a0': ' ',     # nbsp
    '\u2018': "'",     # ’
    '\u2019': "'",     # ‘
    '\u201c': '"',     # "
    '\u201d': '"',     # "
}


def _sanitize(text):
    """Replace unicode glyphs that Helvetica (Latin-1) can't render."""
    if text is None:
        return ''
    s = str(text)
    for u, ascii_equiv in _UNICODE_MAP.items():
        if u in s:
            s = s.replace(u, ascii_equiv)
    # Drop anything still outside Latin-1
    return s.encode('latin-1', 'replace').decode('latin-1')


# =========================================================================
# PUBLIC API
# =========================================================================

def generate_pdf_report(results, network_summary, output_path,
                        title='Hydraulic Analysis Report',
                        engineer_name='', project_name=''):
    """
    Generate a PDF (or HTML fallback) report.

    Parameters match those of ``generate_docx_report`` -- see its docstring
    for the full description of *results* and *network_summary*.
    """
    if HAS_FPDF:
        return _generate_fpdf_report(
            results, network_summary, output_path,
            title=title, engineer_name=engineer_name,
            project_name=project_name,
        )
    else:
        # Fall back to HTML
        html_path = output_path.replace('.pdf', '.html')
        return _generate_html_report(
            results, network_summary, html_path,
            title=title, engineer_name=engineer_name,
            project_name=project_name,
        )


# =========================================================================
# FPDF2 IMPLEMENTATION
# =========================================================================

class _EPANETPdf(FPDF if HAS_FPDF else object):
    """Custom FPDF subclass with header/footer."""

    def __init__(self, report_title='Hydraulic Analysis Report'):
        if not HAS_FPDF:
            return
        super().__init__()
        self._report_title = _sanitize(report_title)

    # Override text-writing methods so callers don't have to sanitize
    # every string they pass in. Helvetica cannot render unicode glyphs
    # that appear freely in our hydraulic data (m^2, deg, mu, >=, --, etc).
    def cell(self, *args, **kw):
        if 'text' in kw:
            kw['text'] = _sanitize(kw['text'])
        elif 'txt' in kw:
            kw['txt'] = _sanitize(kw['txt'])
        elif len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        return super().cell(*args, **kw)

    def multi_cell(self, *args, **kw):
        if 'text' in kw:
            kw['text'] = _sanitize(kw['text'])
        elif 'txt' in kw:
            kw['txt'] = _sanitize(kw['txt'])
        elif len(args) >= 3:
            args = list(args)
            args[2] = _sanitize(args[2])
        return super().multi_cell(*args, **kw)

    def header(self):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 8, self._report_title, align='L')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')


def _generate_fpdf_report(results, network_summary, output_path,
                          title='', engineer_name='', project_name=''):
    cover_title = project_name if project_name else title
    pdf = _EPANETPdf(report_title=cover_title)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ----- COVER -----
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font('Helvetica', 'B', 26)
    pdf.set_text_color(46, 64, 87)
    pdf.cell(0, 14, cover_title, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(6)
    pdf.set_font('Helvetica', '', 14)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 10, 'Prepared using EPANET Hydraulic Analysis Toolkit',
             align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(10)
    if engineer_name:
        pdf.set_font('Helvetica', '', 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, f'Engineer: {engineer_name}', align='C',
                 new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, f'Date: {date.today().strftime("%d %B %Y")}', align='C',
             new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', 'I', 11)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 8, 'Analysis per WSAA Guidelines', align='C',
             new_x='LMARGIN', new_y='NEXT')

    # ----- EXECUTIVE SUMMARY -----
    pdf.add_page()
    _section_heading(pdf, 'Executive Summary')
    _write_pdf_executive_summary(pdf, results, network_summary)

    # ----- SECTION 1: NETWORK DESCRIPTION -----
    pdf.add_page()
    _section_heading(pdf, '1. Network Description')

    _sub_heading(pdf, '1.1 Network Summary')
    _pdf_table(pdf, ['Component', 'Count'], [
        ['Junctions', str(network_summary.get('junctions', 0))],
        ['Reservoirs', str(network_summary.get('reservoirs', 0))],
        ['Tanks', str(network_summary.get('tanks', 0))],
        ['Pipes', str(network_summary.get('pipes', 0))],
        ['Valves', str(network_summary.get('valves', 0))],
        ['Pumps', str(network_summary.get('pumps', 0))],
    ])

    nodes = network_summary.get('nodes', [])
    if nodes:
        _sub_heading(pdf, '1.2 Node Details')
        node_rows = []
        for n in nodes:
            ntype = n.get('type', '')
            elevation = n.get('elevation', n.get('head', '-'))
            demand = n.get('demand_lps', '-')
            node_rows.append([n['id'], ntype.capitalize(), str(elevation), str(demand)])
        _pdf_table(pdf, ['ID', 'Type', 'Elevation (m)', 'Demand (LPS)'], node_rows)

    links = network_summary.get('links', [])
    if links:
        _sub_heading(pdf, '1.3 Pipe / Link Details')
        link_rows = []
        for lk in links:
            link_rows.append([
                lk['id'], lk.get('start', '-'), lk.get('end', '-'),
                str(lk.get('length', '-')), str(lk.get('diameter_mm', '-')),
                str(lk.get('roughness', '-')),
            ])
        _pdf_table(pdf, ['ID', 'Start', 'End', 'Length', 'Dia (mm)', 'Rough.'],
                   link_rows)

    # ----- SECTION 2: STEADY-STATE -----
    steady = results.get('steady_state')
    if steady:
        pdf.add_page()
        _section_heading(pdf, '2. Steady-State Results')

        pressures = steady.get('pressures', {})
        if pressures:
            _sub_heading(pdf, '2.1 Junction Pressures')
            p_rows = [[j, str(d.get('min_m', '-')), str(d.get('max_m', '-')),
                        str(d.get('avg_m', '-'))]
                       for j, d in pressures.items()]
            _pdf_table(pdf, ['Junction', 'Min (m)', 'Max (m)', 'Avg (m)'], p_rows)

        flows = steady.get('flows', {})
        if flows:
            _sub_heading(pdf, '2.2 Pipe Flows')
            f_rows = [[p, str(d.get('min_lps', '-')), str(d.get('max_lps', '-')),
                        str(d.get('avg_lps', '-')), str(d.get('avg_velocity_ms', '-'))]
                       for p, d in flows.items()]
            _pdf_table(pdf, ['Pipe', 'Min LPS', 'Max LPS', 'Avg LPS', 'Vel m/s'],
                       f_rows)

    # ----- SECTION 3: COMPLIANCE -----
    all_compliance = _collect_compliance(results)
    if all_compliance:
        pdf.add_page()
        _section_heading(pdf, '3. Compliance Summary')
        comp_rows = [[c.get('type', 'INFO'), c.get('element', '-'),
                       c.get('message', '')] for c in all_compliance]
        _pdf_table(pdf, ['Status', 'Element', 'Message'], comp_rows)

    # ----- SECTION 4: TRANSIENT -----
    transient = results.get('transient')
    if transient:
        pdf.add_page()
        _section_heading(pdf, '4. Transient Analysis (Water Hammer)')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6,
                 f'Valve: {transient.get("valve", "-")}  |  '
                 f'Closure: {transient.get("closure_time_s", "-")} s  |  '
                 f'Wave speed: {transient.get("wave_speed_ms", "-")} m/s',
                 new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)
        pdf.cell(0, 6,
                 f'Maximum surge: {transient.get("max_surge_m", "-")} m '
                 f'({transient.get("max_surge_kPa", "-")} kPa)',
                 new_x='LMARGIN', new_y='NEXT')
        pdf.ln(4)

        junctions = transient.get('junctions', {})
        if junctions:
            _sub_heading(pdf, '4.1 Junction Surge Data')
            t_rows = [[j, str(d.get('steady_head_m', '-')),
                        str(d.get('max_head_m', '-')),
                        str(d.get('min_head_m', '-')),
                        str(d.get('surge_m', '-')),
                        str(d.get('surge_kPa', '-'))]
                       for j, d in junctions.items()]
            _pdf_table(pdf, ['Junction', 'Steady', 'Max', 'Min', 'Surge m', 'Surge kPa'],
                       t_rows)

        mitigation = transient.get('mitigation', [])
        if mitigation:
            _sub_heading(pdf, '4.2 Mitigation Recommendations')
            for rec in mitigation:
                pdf.set_font('Helvetica', '', 10)
                pdf.cell(6, 6, chr(8226))  # bullet
                pdf.cell(0, 6, rec, new_x='LMARGIN', new_y='NEXT')

    # ----- SECTION 5: FIRE FLOW -----
    fire_flow = results.get('fire_flow')
    if fire_flow:
        pdf.add_page()
        _section_heading(pdf, '5. Fire Flow Analysis')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6,
                 f'Fire node: {fire_flow.get("fire_node", "-")}  |  '
                 f'Flow: {fire_flow.get("fire_flow_lps", "-")} LPS  |  '
                 f'Node pressure: {fire_flow.get("fire_node_pressure_m", "-")} m',
                 new_x='LMARGIN', new_y='NEXT')
        pdf.ln(4)
        residuals = fire_flow.get('residual_pressures', {})
        if residuals:
            ff_rows = [[j, str(p)] for j, p in residuals.items()]
            _pdf_table(pdf, ['Junction', 'Residual Pressure (m)'], ff_rows)

    # ----- SECTION 6: WATER QUALITY -----
    wq = results.get('water_quality')
    if wq:
        pdf.add_page()
        _section_heading(pdf, '6. Water Quality Analysis')
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 6,
                 f'Parameter: {wq.get("parameter", "-")}  |  '
                 f'Duration: {wq.get("duration_hrs", "-")} hrs',
                 new_x='LMARGIN', new_y='NEXT')
        pdf.ln(4)
        jq = wq.get('junction_quality', {})
        if jq:
            wq_rows = [[j, str(d.get('max_age_hrs', '-')),
                         str(d.get('avg_age_hrs', '-'))]
                        for j, d in jq.items()]
            _pdf_table(pdf, ['Junction', 'Max Age (hrs)', 'Avg Age (hrs)'], wq_rows)

    # ----- CONCLUSIONS -----
    pdf.add_page()
    _section_heading(pdf, 'Conclusions')
    for para in _build_conclusions(results):
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, para)
        pdf.ln(3)

    pdf.output(output_path)
    return output_path


# =========================================================================
# FPDF helpers
# =========================================================================

def _write_pdf_executive_summary(pdf, results, network_summary):
    """Write executive summary section in PDF."""
    n_junctions = network_summary.get('junctions', 0)
    n_pipes = network_summary.get('pipes', 0)
    n_reservoirs = network_summary.get('reservoirs', 0)
    n_tanks = network_summary.get('tanks', 0)

    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 6,
        f'This report presents the hydraulic analysis of a water distribution network '
        f'comprising {n_junctions} junctions, {n_pipes} pipes, '
        f'{n_reservoirs} reservoir(s), and {n_tanks} tank(s). '
        f'Analysis was performed in accordance with WSAA WSA 03-2011 guidelines.')
    pdf.ln(4)

    # Compliance overview
    all_compliance = _collect_compliance(results)
    warn_count = sum(1 for c in all_compliance if c.get('type') == 'WARNING')
    crit_count = sum(1 for c in all_compliance if c.get('type') == 'CRITICAL')

    _sub_heading(pdf, 'Compliance Status')
    if crit_count == 0 and warn_count == 0:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 8, 'PASS', new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6,
            'All parameters within WSAA guideline limits: minimum pressure (20 m), '
            'maximum pressure (50 m), and velocity (<2.0 m/s).')
    else:
        if crit_count:
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(204, 0, 0)
            pdf.cell(0, 7, f'{crit_count} CRITICAL issue(s)', new_x='LMARGIN', new_y='NEXT')
        if warn_count:
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(204, 122, 0)
            pdf.cell(0, 7, f'{warn_count} WARNING(s)', new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Key metrics table
    steady = results.get('steady_state')
    if steady:
        pressures = steady.get('pressures', {})
        flows = steady.get('flows', {})
        if pressures:
            _sub_heading(pdf, 'Key Hydraulic Metrics')
            all_min = [d.get('min_m', 0) for d in pressures.values()]
            all_max = [d.get('max_m', 0) for d in pressures.values()]
            metrics = [
                ['Pressure Range', f'{min(all_min):.1f} - {max(all_max):.1f} m'],
                ['WSAA Min (20 m)', 'PASS' if min(all_min) >= 20 else 'FAIL'],
                ['WSAA Max (50 m)', 'PASS' if max(all_max) <= 50 else 'FAIL'],
            ]
            if flows:
                all_vel = [d.get('max_velocity_ms', 0) for d in flows.values()]
                metrics.append(
                    ['Max Velocity', f'{max(all_vel):.2f} m/s '
                     f'({"PASS" if max(all_vel) <= 2.0 else "FAIL"})']
                )
            _pdf_table(pdf, ['Metric', 'Value'], metrics)


def _section_heading(pdf, text):
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(46, 64, 87)
    pdf.cell(0, 10, text, new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _sub_heading(pdf, text):
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(0, 8, text, new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _pdf_table(pdf, headers, rows):
    """Draw a styled table with header shading and alternating row colours."""
    n_cols = len(headers)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable / n_cols
    row_h = 7

    # Header
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(46, 64, 87)
    pdf.set_text_color(255, 255, 255)
    for h in headers:
        pdf.cell(col_w, row_h, h, border=1, fill=True, align='C')
    pdf.ln(row_h)

    # Data rows with alternating background
    pdf.set_font('Helvetica', '', 9)
    for r_idx, row in enumerate(rows):
        # Check for page break
        if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
            pdf.add_page()

        # Alternating row background
        if r_idx % 2 == 0:
            pdf.set_fill_color(244, 246, 248)
            fill = True
        else:
            fill = False

        for c_idx, val in enumerate(row):
            val_str = str(val)[:40]
            # Colour-code compliance status values
            if val_str in ('PASS', 'OK'):
                pdf.set_text_color(0, 128, 0)
                pdf.set_font('Helvetica', 'B', 9)
            elif val_str in ('FAIL', 'CRITICAL'):
                pdf.set_text_color(204, 0, 0)
                pdf.set_font('Helvetica', 'B', 9)
            elif val_str == 'WARNING':
                pdf.set_text_color(204, 122, 0)
                pdf.set_font('Helvetica', 'B', 9)
            else:
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Helvetica', '', 9)

            pdf.cell(col_w, row_h, val_str, border=1, fill=fill, align='C')

        pdf.ln(row_h)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)


# =========================================================================
# HTML FALLBACK
# =========================================================================

def _generate_html_report(results, network_summary, output_path,
                          title='', engineer_name='', project_name=''):
    """Generate an HTML report when fpdf2 is not available."""
    cover_title = project_name if project_name else title
    today = date.today().strftime('%d %B %Y')

    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en"><head><meta charset="UTF-8">',
        f'<title>{cover_title}</title>',
        '<style>',
        'body{font-family:Calibri,Arial,sans-serif;margin:40px;color:#333}',
        'h1{color:#2E4057;border-bottom:2px solid #2E4057;padding-bottom:6px}',
        'h2{color:#444}',
        'table{border-collapse:collapse;width:100%;margin:10px 0 20px}',
        'th{background:#2E4057;color:#fff;padding:8px;text-align:center}',
        'td{border:1px solid #ccc;padding:6px;text-align:center}',
        'tr:nth-child(even){background:#f4f6f8}',
        '.ok{color:green;font-weight:bold}',
        '.warning{color:#CC7A00;font-weight:bold}',
        '.critical{color:#CC0000;font-weight:bold}',
        '.cover{text-align:center;margin-top:120px}',
        '.cover h1{font-size:2em;border:none}',
        '@media print{.page-break{page-break-before:always}}',
        '</style></head><body>',
    ]

    # Cover
    html_parts.append('<div class="cover">')
    html_parts.append(f'<h1>{cover_title}</h1>')
    html_parts.append('<p>Prepared using EPANET Hydraulic Analysis Toolkit</p>')
    if engineer_name:
        html_parts.append(f'<p>Engineer: {engineer_name}</p>')
    html_parts.append(f'<p>Date: {today}</p>')
    html_parts.append('<p><em>Analysis per WSAA Guidelines</em></p>')
    html_parts.append('</div>')

    # Section 1
    html_parts.append('<div class="page-break"></div>')
    html_parts.append('<h1>1. Network Description</h1>')
    html_parts.append(_html_table(
        ['Component', 'Count'],
        [['Junctions', network_summary.get('junctions', 0)],
         ['Reservoirs', network_summary.get('reservoirs', 0)],
         ['Tanks', network_summary.get('tanks', 0)],
         ['Pipes', network_summary.get('pipes', 0)],
         ['Valves', network_summary.get('valves', 0)]],
    ))

    # Section 2: Steady
    steady = results.get('steady_state')
    if steady:
        html_parts.append('<div class="page-break"></div>')
        html_parts.append('<h1>2. Steady-State Results</h1>')
        pressures = steady.get('pressures', {})
        if pressures:
            html_parts.append('<h2>2.1 Junction Pressures</h2>')
            html_parts.append(_html_table(
                ['Junction', 'Min (m)', 'Max (m)', 'Avg (m)'],
                [[j, d.get('min_m'), d.get('max_m'), d.get('avg_m')]
                 for j, d in pressures.items()],
            ))

    # Section 3: Compliance
    all_compliance = _collect_compliance(results)
    if all_compliance:
        html_parts.append('<div class="page-break"></div>')
        html_parts.append('<h1>3. Compliance Summary</h1>')
        rows_html = []
        for c in all_compliance:
            ctype = c.get('type', 'INFO')
            css = ctype.lower()
            rows_html.append(
                f'<tr><td class="{css}">{ctype}</td>'
                f'<td>{c.get("element", "-")}</td>'
                f'<td>{c.get("message", "")}</td></tr>'
            )
        html_parts.append(
            '<table><tr><th>Status</th><th>Element</th><th>Message</th></tr>'
            + ''.join(rows_html) + '</table>'
        )

    # Conclusions
    html_parts.append('<div class="page-break"></div>')
    html_parts.append('<h1>Conclusions</h1>')
    for para in _build_conclusions(results):
        html_parts.append(f'<p>{para}</p>')

    html_parts.append('</body></html>')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))

    return output_path


def _html_table(headers, rows):
    parts = ['<table><tr>']
    for h in headers:
        parts.append(f'<th>{h}</th>')
    parts.append('</tr>')
    for row in rows:
        parts.append('<tr>')
        for val in row:
            parts.append(f'<td>{val}</td>')
        parts.append('</tr>')
    parts.append('</table>')
    return ''.join(parts)


# =========================================================================
# Shared helpers (duplicated from docx_report to keep modules independent)
# =========================================================================

def _collect_compliance(results):
    items = []
    for key in ('steady_state', 'transient', 'fire_flow', 'water_quality'):
        sub = results.get(key)
        if sub and 'compliance' in sub:
            items.extend(sub['compliance'])
    return items


def _build_conclusions(results):
    paragraphs = []
    all_compliance = _collect_compliance(results)

    ok_count = sum(1 for c in all_compliance if c.get('type') == 'OK')
    warn_count = sum(1 for c in all_compliance if c.get('type') == 'WARNING')
    crit_count = sum(1 for c in all_compliance if c.get('type') == 'CRITICAL')

    if crit_count:
        paragraphs.append(
            f'CRITICAL: {crit_count} critical issue(s) were identified that '
            f'require immediate engineering attention before the network can be '
            f'considered compliant with WSAA guidelines.'
        )
    if warn_count:
        paragraphs.append(
            f'{warn_count} warning(s) were identified. These should be reviewed '
            f'and addressed where practicable to improve network performance.'
        )
    if ok_count and not crit_count and not warn_count:
        paragraphs.append(
            'All analyses passed compliance checks. The network meets '
            'WSAA guideline requirements for the scenarios tested.'
        )
    if not paragraphs:
        paragraphs.append(
            'Analysis complete. Review the detailed results in the '
            'preceding sections for engineering assessment.'
        )
    return paragraphs
