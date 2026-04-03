"""
Dark theme configuration for the EPANET Dashboard.
Ports the CSS custom properties from dashboard.html to NiceGUI/Quasar styling.
"""

# Color palette
COLORS = {
    'bg': '#0f1419',
    'card': '#1a2332',
    'border': '#2d3748',
    'text': '#e2e8f0',
    'muted': '#8892a4',
    'accent': '#3b82f6',
    'green': '#10b981',
    'red': '#ef4444',
    'orange': '#f59e0b',
    'cyan': '#06b6d4',
}

# Plotly chart layout template
PLOTLY_LAYOUT = {
    'paper_bgcolor': COLORS['card'],
    'plot_bgcolor': '#0d1117',
    'font': {'color': COLORS['muted'], 'size': 11},
    'margin': {'t': 35, 'r': 20, 'b': 45, 'l': 55},
    'xaxis': {'gridcolor': COLORS['border'], 'zerolinecolor': COLORS['border']},
    'yaxis': {'gridcolor': COLORS['border'], 'zerolinecolor': COLORS['border']},
    'legend': {'bgcolor': 'rgba(0,0,0,0)', 'font': {'size': 10}},
}

# Chart color sequence for multi-line plots
CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4',
                '#84cc16', '#f97316', '#a855f7']

# CSS for the entire app
APP_CSS = """
body {
    background-color: #0f1419 !important;
}
.q-page {
    background-color: #0f1419 !important;
}
.q-card {
    background-color: #1a2332 !important;
    border: 1px solid #2d3748 !important;
}
.q-tab-panels {
    background-color: transparent !important;
}
.q-tab-panel {
    padding: 0 !important;
}
.q-tabs {
    background-color: #1a2332 !important;
}
.q-field__control {
    background-color: #0f1419 !important;
    color: #e2e8f0 !important;
}
.q-field__label {
    color: #8892a4 !important;
}
.metric-card {
    text-align: center;
    padding: 12px;
}
.metric-value {
    font-size: 28px;
    font-weight: 700;
}
.metric-unit {
    font-size: 12px;
    color: #8892a4;
}
.metric-label {
    font-size: 11px;
    color: #8892a4;
    margin-top: 2px;
}
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: #8892a4;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.compliance-ok { color: #10b981; }
.compliance-warning { color: #f59e0b; }
.compliance-critical { color: #ef4444; }
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.badge-blue { background: #3b82f6; color: white; }
.badge-green { background: #065f46; color: #6ee7b7; }
"""
