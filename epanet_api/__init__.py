"""
EPANET Hydraulic Analysis API — Package
=========================================
Unified Python API wrapping WNTR, EPyT, and TSNet for hydraulic
and transient analysis. Designed for Australian engineering practice.

Usage:
    from epanet_api import HydraulicAPI
    api = HydraulicAPI()
    api.create_network(...)
    results = api.run_steady_state()
"""

import sys
import io
import os

import numpy as np
import wntr
import matplotlib
matplotlib.use('Agg')

# Force UTF-8 output on Windows
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from epanet_api.core import CoreMixin
from epanet_api.analysis import AnalysisMixin
from epanet_api.slurry import SlurryMixin
from epanet_api.compliance import ComplianceMixin
from epanet_api.assets import AssetsMixin
from epanet_api.advanced import AdvancedMixin
from epanet_api.topology import TopologyMixin
from epanet_api.resilience import ResilienceMixin
from epanet_api.calibration import CalibrationMixin
from epanet_api.forecasting import ForecastingMixin
from epanet_api.surge import SurgeMixin
from epanet_api.comparison import ComparisonMixin
from epanet_api.terrain import TerrainMixin
from epanet_api.pumping import PumpingMixin
from epanet_api.water_quality import WaterQualityMixin


class HydraulicAPI(CoreMixin, AnalysisMixin, SlurryMixin, ComplianceMixin,
                   AssetsMixin, AdvancedMixin, TopologyMixin, ResilienceMixin,
                   CalibrationMixin, ForecastingMixin, SurgeMixin, ComparisonMixin,
                   TerrainMixin, PumpingMixin, WaterQualityMixin):
    """Unified API for EPANET hydraulic and transient analysis."""

    # Australian standard unit defaults
    DEFAULTS = {
        'flow_units': 'LPS',          # Litres per second
        'headloss': 'H-W',            # Hazen-Williams
        'min_pressure_m': 20,          # WSAA minimum pressure (m)
        'max_pressure_m': 50,          # WSAA maximum static pressure (m)
        'max_velocity_ms': 2.0,        # Maximum pipe velocity (m/s)
        'min_velocity_ms': 0.6,        # Minimum velocity to prevent sediment (WSAA)
        'pipe_rating_kPa': 3500,       # PN35 ductile iron
        'wave_speed_ms': 1100,         # AS 2280 minimum for ductile iron
    }

    def __init__(self, work_dir=None):
        self.work_dir = work_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_dir = os.path.join(self.work_dir, 'models')
        self.output_dir = os.path.join(self.work_dir, 'output')
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        self.wn = None
        self.tm = None
        self.steady_results = None
        self.transient_results = None
        self._inp_file = None
        # Initialize terrain mixin state
        TerrainMixin.__init__(self)
        
        self.DEFAULTS = dict(HydraulicAPI.DEFAULTS)
        self.load_settings()

    def load_settings(self):
        """Load user settings from settings.json."""
        import json
        self.settings = {
            'units': 'LPS',
            'theme': 'Dark',
            'default_roughness': 140
        }
        if os.path.exists('settings.json'):
            try:
                with open('settings.json', 'r') as f:
                    self.settings.update(json.load(f))
            except:
                pass

    def save_settings(self):
        """Save current settings to settings.json."""
        import json
        try:
            with open('settings.json', 'w') as f:
                json.dump(self.settings, f, indent=4)
        except:
            pass


__all__ = ['HydraulicAPI']
