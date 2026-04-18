"""
Water Quality Mixin — Chlorine Decay, Age of Water, and Dosing
============================================================
Provides advanced water quality modeling:
1. Chemical concentration tracking (Chlorine, Fluoride).
2. Water Age (residence time) analysis.
3. Source tracing.
4. Reaction kinetics (bulk and wall decay).
"""

import wntr
import logging

logger = logging.getLogger(__name__)

class WaterQualityMixin:
    def set_water_quality_mode(self, mode, chemical_name='Chlorine', units='mg/L'):
        """
        Set the water quality analysis mode.
        mode: 'AGE', 'CHEMICAL', 'TRACE', or 'NONE'
        """
        if self.wn is None:
            return
            
        self.wn.options.quality.parameter = mode
        if mode == 'CHEMICAL':
            self.wn.options.quality.chemical_name = chemical_name
            self.wn.options.quality.units = units
        elif mode == 'TRACE':
            # Default to first reservoir if trace node not specified
            sources = self.wn.reservoir_name_list
            if sources:
                self.wn.options.quality.trace_node = sources[0]
                
    def run_water_quality_analysis(self):
        """
        Run a water quality simulation using the Epanet solver.
        Note: This typically requires an EPS (Extended Period Simulation).
        """
        if self.wn is None:
            return {'error': 'No network loaded.'}
            
        # Ensure we have a reasonable duration for quality (e.g. 48 hours)
        if self.wn.options.time.duration < 24 * 3600:
            logger.info("Increasing simulation duration to 48 hours for water quality analysis.")
            self.wn.options.time.duration = 48 * 3600
            
        sim = wntr.sim.EpanetSimulator(self.wn)
        try:
            results = sim.run_sim()
            quality = results.node['quality']
            
            # Build results dict
            res = {
                'quality': {},
                'mode': self.wn.options.quality.parameter,
                'duration_hrs': self.wn.options.time.duration / 3600
            }
            
            for node_name in self.wn.node_name_list:
                node_q = quality[node_name]
                res['quality'][node_name] = {
                    'min': round(float(node_q.min()), 3),
                    'max': round(float(node_q.max()), 3),
                    'avg': round(float(node_q.mean()), 3),
                    'final': round(float(node_q.iloc[-1]), 3)
                }
            return res
        except Exception as e:
            logger.error(f"Water quality simulation failed: {e}")
            return {'error': str(e)}

    def set_source_concentration(self, node_name, concentration):
        """Set a source node chemical concentration."""
        if self.wn is None:
            return
        node = self.wn.get_node(node_name)
        # Source types: 'MASS', 'CONCEN', 'FLOWPACED', 'SETPOINT'
        # We default to CONCEN for simple reservoirs/tanks
        self.wn.add_source('Source-' + node_name, node_name, 'CONCEN', concentration)

    def set_global_reaction_coeffs(self, bulk_coeff=-0.5, wall_coeff=-0.1):
        """
        Set global reaction coefficients.
        bulk_coeff: 1/day (typical -0.1 to -1.0 for chlorine)
        wall_coeff: m/day (typical -0.01 to -0.1)
        """
        if self.wn is None:
            return
        self.wn.options.reaction.bulk_coeff = bulk_coeff
        self.wn.options.reaction.wall_coeff = wall_coeff
        
    def set_pipe_reaction_coeffs(self, pipe_id, bulk_coeff=None, wall_coeff=None):
        """Set specific reaction coefficients for a pipe."""
        if self.wn is None:
            return
        pipe = self.wn.get_link(pipe_id)
        if bulk_coeff is not None:
            pipe.bulk_coeff = bulk_coeff
        if wall_coeff is not None:
            pipe.wall_coeff = wall_coeff

    def optimize_source_dose(self, target_min_residual=0.2, max_iterations=10):
        """
        Find the minimum source dose to achieve target residual at all nodes.
        Uses a simple binary search or iterative approach.
        """
        if self.wn is None:
            return None
            
        # Get all sources
        source_names = list(self.wn.sources.keys())
        if not source_names:
            return None
            
        low = 0.2
        high = 5.0
        best_dose = high
        
        for _ in range(max_iterations):
            mid = (low + high) / 2
            # Set all sources to mid
            for sname in source_names:
                self.wn.get_source(sname).strength_timeseries.base_value = mid
            
            res = self.run_water_quality_analysis()
            if 'error' in res:
                break
                
            # Find minimum residual in network
            min_res = min([d['final'] for d in res['quality'].values()])
            
            if min_res >= target_min_residual:
                best_dose = mid
                high = mid
            else:
                low = mid
                
        return round(best_dose, 2)

    def generate_quality_compliance_report(self):
        """
        Generate a compliance report based on ADWG (Australian Drinking Water Guidelines).
        """
        res = self.run_water_quality_analysis()
        if 'error' in res:
            return res
            
        report = {
            'summary': {
                'total_nodes': 0,
                'failing_nodes': 0,
                'compliance_rate': 0.0,
                'parameter': res['mode']
            },
            'details': []
        }
        
        mode = res['mode']
        
        for name, data in res['quality'].items():
            node = self.wn.get_node(name)
            # Only report on junctions with demand (delivery points)
            if hasattr(node, 'demand_timeseries_list') and node.demand_timeseries_list:
                report['summary']['total_nodes'] += 1
                
                status = "PASS"
                reason = ""
                
                val = data['final']
                if mode == 'CHEMICAL':
                    if val < 0.2:
                        status = "FAIL"
                        reason = "Residual below 0.2 mg/L (ADWG Min)"
                    elif val > 5.0:
                        status = "FAIL"
                        reason = "Residual above 5.0 mg/L (ADWG Max)"
                elif mode == 'AGE':
                    if val > 120.0: # 5 days
                        status = "FAIL"
                        reason = "Water age exceeds 120h (Stagnation risk)"
                        
                if status == "FAIL":
                    report['summary']['failing_nodes'] += 1
                    
                report['details'].append({
                    'node_id': name,
                    'value': val,
                    'status': status,
                    'reason': reason
                })
                
        if report['summary']['total_nodes'] > 0:
            report['summary']['compliance_rate'] = round(
                (1 - report['summary']['failing_nodes'] / report['summary']['total_nodes']) * 100, 1)
                
        return report

    def run_multi_species_analysis(self, species_list=None):
        """
        Run sequential simulations for multiple chemical species.
        """
        if species_list is None:
            species_list = ['Chlorine', 'Fluoride']
            
        multi_results = {}
        for species in species_list:
            self.set_water_quality_mode('CHEMICAL', chemical_name=species)
            res = self.run_water_quality_analysis()
            if 'error' not in res:
                multi_results[species] = res
                
        return multi_results

    def suggest_booster_stations(self, min_threshold=0.2):
        """
        Identify nodes where residual is low and suggest booster placement.
        """
        res = self.run_water_quality_analysis()
        if 'error' in res:
            return []
            
        failing_nodes = []
        for name, data in res['quality'].items():
            if data['final'] < min_threshold:
                failing_nodes.append(name)
                
        if not failing_nodes:
            return []
            
        # Suggest placement at junctions that are "entry points" to failing zones
        suggestions = []
        seen_zones = set()
        
        for node_name in failing_nodes:
            # Find the first upstream junction that is NOT failing (the boundary)
            curr = node_name
            found = False
            for _ in range(5): # limit search depth
                links = self.wn.get_links_for_node(curr)
                upstream_found = False
                for lname in links:
                    link = self.wn.get_link(lname)
                    # Simple heuristic: follow start_node if we are end_node
                    if link.end_node_name == curr:
                        prev = link.start_node_name
                        if prev not in failing_nodes:
                            if curr not in seen_zones:
                                suggestions.append({
                                    'node_id': curr,
                                    'residual': res['quality'][curr]['final'],
                                    'reason': f"Entry point to low-residual zone ({len(failing_nodes)} nodes)"
                                })
                                seen_zones.add(curr)
                            found = True
                            break
                        curr = prev
                        upstream_found = True
                        break
                if found or not upstream_found:
                    break
                    
        return suggestions
