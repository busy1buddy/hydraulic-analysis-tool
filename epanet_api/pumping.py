"""
Pumping Mixin — Pump Selection, TDH, and System Curves
=====================================================
Provides advanced pumping analysis:
1. Total Dynamic Head (TDH) calculation.
2. Automated System Curve generation.
3. Pump database integration and duty point matching.
4. NPSH and cavitation risk assessment.
"""

import math
import numpy as np
import logging

logger = logging.getLogger(__name__)

class PumpingMixin:
    def calculate_required_tdh(self, pump_id, target_flow_lps):
        """
        Calculate the required Total Dynamic Head (TDH) for a pump to 
        achieve a target flow rate in the current network.
        
        Logic:
        1. Find path from source (suction) to destination (discharge).
        2. Calculate Static Head (Z_discharge - Z_suction).
        3. Calculate Friction Headloss at target_flow_lps.
        4. TDH = Static + Friction.
        """
        if self.wn is None:
            return None

        try:
            pump = self.wn.get_link(pump_id)
            suction_node = pump.start_node_name
            discharge_node = pump.end_node_name
            
            # Find the most relevant source and sink for this pump
            # We use BFS to find the nearest Reservoir/Tank upstream and downstream
            source_node = self._find_nearest_fixed_head(suction_node, upstream=True)
            sink_node = self._find_nearest_fixed_head(discharge_node, upstream=False)
            
            if not source_node or not sink_node:
                logger.warning(f"Could not find fixed-head source/sink for pump {pump_id}")
                return None
                
            # Use networkx pathfinding from CoreMixin
            path_profile = self.get_path_profile(source_node, sink_node)
            if not path_profile:
                return None
                
            # Static Head
            z_source = self.wn.get_node(source_node).elevation
            if hasattr(self.wn.get_node(source_node), 'base_head'):
                z_source = self.wn.get_node(source_node).base_head
                
            z_sink = self.wn.get_node(sink_node).elevation
            if hasattr(self.wn.get_node(sink_node), 'base_head'):
                z_sink = self.wn.get_node(sink_node).base_head
                
            static_head = z_sink - z_source
            
            # Friction Headloss along path at target flow
            # We iterate through pipes in the path and calculate headloss
            total_friction_loss = 0
            path_nodes = path_profile['labels']
            for i in range(len(path_nodes)-1):
                n1 = path_nodes[i]
                n2 = path_nodes[i+1]
                
                # Find link between nodes
                for link_name in self.wn.get_links_for_node(n1):
                    link = self.wn.get_link(link_name)
                    if link.start_node_name == n2 or link.end_node_name == n2:
                        if link.link_type == 'Pipe':
                            # Hazen-Williams: hl = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)
                            Q_m3s = target_flow_lps / 1000.0
                            C = link.roughness
                            D = link.diameter
                            L = link.length
                            if D > 0 and C > 0:
                                hl = (10.67 * L * Q_m3s**1.852) / (C**1.852 * D**4.87)
                                total_friction_loss += hl
                        break
            
            tdh = static_head + total_friction_loss
            return {
                'pump_id': pump_id,
                'target_flow_lps': target_flow_lps,
                'static_head_m': round(static_head, 2),
                'friction_head_m': round(total_friction_loss, 2),
                'tdh_m': round(tdh, 2),
                'source': source_node,
                'sink': sink_node
            }
            
        except Exception as e:
            logger.error(f"TDH calculation failed: {e}")
            return None

    def calculate_energy_cost(self, power_kw, duty_hours_per_day=24, rate_aud_kwh=0.25):
        """
        Estimate annual energy cost for the pump.
        """
        daily_kwh = power_kw * duty_hours_per_day
        annual_kwh = daily_kwh * 365
        annual_cost = annual_kwh * rate_aud_kwh
        return {
            'annual_kwh': round(annual_kwh, 0),
            'annual_cost_aud': round(annual_cost, 0)
        }

    def check_cavitation_risk(self, pump_id, npsha):
        """
        Check if NPSHa is sufficient compared to NPSHr.
        Returns status and recommended margin check.
        """
        from data.pump_curves import PUMP_DATABASE
        pump = PUMP_DATABASE.get(pump_id)
        if not pump or 'npshr_m' not in pump:
            return None
            
        npshr = pump['npshr_m']
        margin = npsha - npshr
        
        status = "Safe"
        color = "#a6e3a1"
        if margin < 1.0:
            status = "Warning: Low NPSH Margin"
            color = "#f9e2af"
        if margin < 0.2:
            status = "CRITICAL: CAVITATION RISK"
            color = "#f38ba8"
            
        return {
            'npshr_m': npshr,
            'margin_m': round(margin, 2),
            'status': status,
            'color': color
        }

    def calculate_npsha(self, pump_id, flow_lps, temp_c=20):
        """
        Calculate Net Positive Suction Head Available (NPSHa).
        NPSHa = H_abs_suction - H_vapor
        """
        if self.wn is None:
            return None
            
        try:
            pump = self.wn.get_link(pump_id)
            suction_node = pump.start_node_name
            
            # 1. Find suction source
            source_node = self._find_nearest_fixed_head(suction_node, upstream=True)
            if not source_node:
                return None
                
            source = self.wn.get_node(source_node)
            z_source = source.elevation
            if hasattr(source, 'base_head'):
                z_source = source.base_head
                
            # 2. Suction Headloss
            # Simplified: assume path from source to suction_node
            path_profile = self.get_path_profile(source_node, suction_node)
            h_friction_suction = 0
            if path_profile:
                path_nodes = path_profile['labels']
                for i in range(len(path_nodes)-1):
                    n1, n2 = path_nodes[i], path_nodes[i+1]
                    for link_name in self.wn.get_links_for_node(n1):
                        link = self.wn.get_link(link_name)
                        if link.start_node_name == n2 or link.end_node_name == n2:
                            if link.link_type == 'Pipe':
                                Q_m3s = flow_lps / 1000.0
                                C, D, L = link.roughness, link.diameter, link.length
                                if D > 0:
                                    h_friction_suction += (10.67 * L * Q_m3s**1.852) / (C**1.852 * D**4.87)
                            break
            
            # 3. Atmospheric Pressure (Standard ~10.33m at sea level)
            # Future: adjust for altitude
            h_atmos = 10.33 
            
            # 4. Vapor Pressure (m) - Water
            # Approx: 0.24m at 20C, 0.43m at 30C, 0.75m at 40C
            v_pressures = {10: 0.12, 20: 0.24, 30: 0.43, 40: 0.75, 50: 1.25, 60: 2.0}
            h_vapor = v_pressures.get(int(round(temp_c/10)*10), 0.24)
            
            # NPSHa = (Z_source + H_atmos - H_friction_suction) - Z_pump - H_vapor
            z_pump = self.wn.get_node(suction_node).elevation
            npsha = (z_source + h_atmos - h_friction_suction) - z_pump - h_vapor
            
            return round(npsha, 2)
            
        except Exception as e:
            logger.error(f"NPSHa calculation failed: {e}")
            return None

    def analyze_bep_proximity(self, pump_id, flow_lps):
        """
        Evaluate if current flow is within the preferred operating region (POR).
        POR is typically 70% to 120% of BEP.
        """
        from data.pump_curves import PUMP_DATABASE
        pump = PUMP_DATABASE.get(pump_id)
        if not pump or 'efficiency_points' not in pump:
            return None
            
        eff_points = pump['efficiency_points']
        flows = [p[0] for p in eff_points]
        effs = [p[1] for p in eff_points]
        
        # Find BEP (Best Efficiency Point)
        max_idx = np.argmax(effs)
        bep_flow = flows[max_idx]
        bep_eff = effs[max_idx]
        
        if bep_flow == 0:
            return None
            
        ratio = flow_lps / bep_flow
        
        status = "Optimal"
        color = "#a6e3a1" # green
        if ratio < 0.7 or ratio > 1.2:
            status = "Warning: Outside POR"
            color = "#f9e2af" # yellow
        if ratio < 0.5 or ratio > 1.4:
            status = "Critical: High Vibration Risk"
            color = "#f38ba8" # red
            
        return {
            'bep_flow_lps': round(bep_flow, 1),
            'bep_efficiency_pct': round(bep_eff, 1),
            'current_ratio_pct': round(ratio * 100, 1),
            'status': status,
            'color': color
        }

    def solve_operating_point(self, pump_id, system_curve, speed_pct=100):
        """
        Find the exact duty point (Q, H) where pump curve meets system curve.
        """
        from data.pump_curves import get_pump_head, get_pump_efficiency
        
        if not system_curve:
            return None
            
        s_flows = [p[0] for p in system_curve]
        s_heads = [p[1] for p in system_curve]
        
        # Define residual function: f(Q) = PumpHead(Q) - SystemHead(Q)
        def residual(q):
            p_head = get_pump_head(pump_id, q, speed_pct)
            s_head = np.interp(q, s_flows, s_heads)
            return p_head - s_head
            
        # High-resolution search for root
        q_min = s_flows[0]
        q_max = s_flows[-1]
        
        # Check if root exists in range
        if residual(q_min) * residual(q_max) > 0:
            # No intersection in range or pump is always below/above system
            return None
            
        # Binary search for root
        from scipy.optimize import brentq
        try:
            best_q = brentq(residual, q_min, q_max, xtol=0.01)
        except ImportError:
            # Fallback to binary search if scipy missing
            low, high = q_min, q_max
            for _ in range(20):
                mid = (low + high) / 2
                if residual(mid) > 0:
                    low = mid
                else:
                    high = mid
            best_q = (low + high) / 2
            
        head = get_pump_head(pump_id, best_q, speed_pct)
        eff = get_pump_efficiency(pump_id, best_q) or 0
        
        return {
            'flow_lps': round(best_q, 2),
            'head_m': round(head, 2),
            'efficiency_pct': round(eff, 2),
            'pump_id': pump_id
        }

    def generate_system_curve_from_network(self, pump_id, max_flow_lps=None, points=20):
        """
        Generate a system curve (TDH vs Flow) by iterating through flow rates.
        """
        if max_flow_lps is None:
            # Estimate max flow from connected pipes or current results
            max_flow_lps = 100.0 # default
            
        flows = np.linspace(0, max_flow_lps, points)
        curve = []
        
        for q in flows:
            res = self.calculate_required_tdh(pump_id, q)
            if res:
                curve.append((q, res['tdh_m']))
            else:
                curve.append((q, 0.0))
                
        return curve

    def _find_nearest_fixed_head(self, start_node, upstream=True):
        """Find the nearest Reservoir or Tank using BFS."""
        visited = {start_node}
        queue = [start_node]
        
        while queue:
            curr = queue.pop(0)
            node = self.wn.get_node(curr)
            if node.node_type in ['Reservoir', 'Tank']:
                return curr
                
            # Get neighbors
            for link_name in self.wn.get_links_for_node(curr):
                link = self.wn.get_link(link_name)
                if upstream:
                    neighbor = link.start_node_name if link.end_node_name == curr else None
                else:
                    neighbor = link.end_node_name if link.start_node_name == curr else None
                    
                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return None
