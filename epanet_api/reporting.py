"""
Reporting Engine — Automated Comparison Reporting
=================================================
Consolidates batch scenario results into professional documents (CSV, Excel, PDF).
Uses pandas for data aggregation and reportlab for PDF generation.
"""

import os
import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

class ReportingEngine:
    """Engine for generating hydraulic analysis reports from multiple scenarios."""
    
    def __init__(self, scenarios):
        """
        Parameters
        ----------
        scenarios : list of ScenarioData
        """
        self.scenarios = scenarios

    def generate_summary_df(self):
        """
        Generate a pandas DataFrame summarizing all scenarios.
        """
        data = []
        for sc in self.scenarios:
            row = {
                'Scenario': sc.name,
                'Demand (x)': f"{sc.demand_multiplier:.1f}",
                'Metal Age (yr)': sc.metal_age,
                'Plastic Age (yr)': sc.plastic_age
            }
            if sc.results:
                pressures = sc.results.get('pressures', {})
                flows = sc.results.get('flows', {})
                compliance = sc.results.get('compliance', [])
                slurry_data = sc.results.get('slurry', {})
                
                all_p_min = [p.get('min_m', 0) for p in pressures.values()]
                all_p_max = [p.get('max_m', 0) for p in pressures.values()]
                
                all_v = []
                for pid, f in flows.items():
                    sd = slurry_data.get(pid)
                    # Prefer slurry velocity if available (Session 28)
                    v = sd.get('velocity_ms', f.get('max_velocity_ms', 0)) if sd else f.get('max_velocity_ms', 0)
                    all_v.append(v)
                
                row['Min P (m)'] = round(min(all_p_min), 1) if all_p_min else 0
                row['Max P (m)'] = round(max(all_p_max), 1) if all_p_max else 0
                row['Max V (m/s)'] = round(max(all_v), 2) if all_v else 0
                row['WSAA Issues'] = sum(1 for c in compliance if c.get('type') in ('WARNING', 'CRITICAL'))
                
                # Compliance breakdown
                crit = sum(1 for c in compliance if c.get('type') == 'CRITICAL')
                warn = sum(1 for c in compliance if c.get('type') == 'WARNING')
                row['Status'] = "FAIL" if crit > 0 else ("WARN" if warn > 0 else "PASS")
            else:
                row.update({
                    'Min P (m)': '--',
                    'Max P (m)': '--',
                    'Max V (m/s)': '--',
                    'WSAA Issues': '--',
                    'Status': 'No Data'
                })
            data.append(row)
        return pd.DataFrame(data)

    def export_csv(self, path):
        """Export scenario summary to CSV."""
        df = self.generate_summary_df()
        df.to_csv(path, index=False)
        return path

    def export_excel(self, path):
        """Export scenario summary to Excel with multiple sheets."""
        df_summary = self.generate_summary_df()
        
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Optionally add detailed results for each scenario as separate sheets
            # For brevity in this session, we only add a 'Detailed' sheet for the first scenario
            # if multiple exist.
            if len(self.scenarios) > 0 and self.scenarios[0].results:
                sc = self.scenarios[0]
                p_df = pd.DataFrame.from_dict(sc.results.get('pressures', {}), orient='index')
                p_df.to_excel(writer, sheet_name=f'Nodes_{sc.name[:10]}')
                
                f_df = pd.DataFrame.from_dict(sc.results.get('flows', {}), orient='index')
                f_df.to_excel(writer, sheet_name=f'Pipes_{sc.name[:10]}')
        
        return path

    def export_pdf(self, path):
        """Export professional PDF report with tables and branding."""
        df = self.generate_summary_df()
        
        # Setup doc
        doc = SimpleDocTemplate(path, pagesize=landscape(A4),
                                rightMargin=30, leftMargin=30,
                                topMargin=30, bottomMargin=30)
        elements = []
        styles = getSampleStyleSheet()
        
        # Header Style
        header_style = styles['Heading1']
        header_style.alignment = 1 # Center
        
        # Title
        title = Paragraph(f"Hydraulic Network Analysis: Comparative Scenario Report", header_style)
        elements.append(title)
        
        # Subtitle
        sub_style = styles['Normal']
        sub_style.alignment = 1
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subtitle = Paragraph(f"Generated on: {date_str} | Total Scenarios: {len(self.scenarios)}", sub_style)
        elements.append(subtitle)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Summary Table
        # Convert DF to list of lists for ReportLab
        data = [df.columns.tolist()] + df.values.tolist()
        
        # Determine column widths
        col_widths = [1.2*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch]
        
        t = Table(data, colWidths=col_widths)
        
        # Styling the table
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e1e2e")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f5f5f5")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ])
        
        # Conditional formatting for Status column (last column)
        for i, row in enumerate(df.itertuples(), start=1):
            if row.Status == "FAIL":
                style.add('TEXTCOLOR', (8, i), (8, i), colors.red)
                style.add('FONTNAME', (8, i), (8, i), 'Helvetica-Bold')
            elif row.Status == "WARN":
                style.add('TEXTCOLOR', (8, i), (8, i), colors.orange)
            elif row.Status == "PASS":
                style.add('TEXTCOLOR', (8, i), (8, i), colors.darkgreen)
        
        t.setStyle(style)
        elements.append(t)
        
        # Disclaimer / Notes
        elements.append(Spacer(1, 0.5 * inch))
        note_style = styles['Italic']
        note_style.fontSize = 8
        note_style.textColor = colors.grey
        note = Paragraph(
            "Note: This report compares multiple network states including demand escalation and material aging. "
            "Results are based on steady-state hydraulic simulation via EPANET/WNTR. "
            "WSAA compliance refers to Australian water industry standards for pressure and velocity.",
            note_style
        )
        elements.append(note)
        
        doc.build(elements)
        return path
