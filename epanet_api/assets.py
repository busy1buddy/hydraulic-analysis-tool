import os, csv


class AssetsMixin:

    # =========================================================================
    # REHABILITATION PRIORITISATION
    # =========================================================================

    def set_pipe_condition(self, pipe_id, install_year=None, condition_score=None,
                           break_history=0, material=None):
        """
        Set asset condition data for a pipe.

        Parameters
        ----------
        pipe_id : str
            Pipe ID in the network
        install_year : int or None
            Year of installation
        condition_score : float or None
            Condition grade 1 (new) to 5 (failed) per WSAA
        break_history : int
            Number of recorded breaks/failures
        material : str or None
            Pipe material (e.g., 'AC', 'CI', 'DI', 'PVC', 'PE')
        """
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}
        self._pipe_conditions[pipe_id] = {
            'install_year': install_year,
            'condition_score': condition_score,
            'break_history': break_history,
            'material': material,
        }

    def get_pipe_conditions(self):
        """Return all pipe condition data."""
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}
        return dict(self._pipe_conditions)

    def import_pipe_conditions_csv(self, csv_path):
        """
        Import pipe condition data from CSV.

        Expected columns: pipe_id, install_year, condition_score,
        break_history, material
        """
        import csv
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}

        count = 0
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row.get('pipe_id', '').strip()
                if not pid:
                    continue
                self._pipe_conditions[pid] = {
                    'install_year': int(row['install_year']) if row.get('install_year') else None,
                    'condition_score': float(row['condition_score']) if row.get('condition_score') else None,
                    'break_history': int(row.get('break_history', 0) or 0),
                    'material': row.get('material', '').strip() or None,
                }
                count += 1
        return count

    def prioritize_rehabilitation(self, results=None, current_year=None):
        """
        Score and rank pipes for rehabilitation based on:
        - Age (years since installation)
        - Condition score (1-5 WSAA scale)
        - Break history (number of failures)
        - Hydraulic performance (headloss, velocity)

        Returns list of dicts sorted by priority score (highest = most urgent).

        Scoring formula:
          priority = (age_score × 0.25) + (condition_score × 0.30)
                   + (break_score × 0.25) + (hydraulic_score × 0.20)

        All component scores normalised to 0-100 range.
        Ref: WSAA Asset Management Guidelines, IPWEA Practice Note 7
        """
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if current_year is None:
            from datetime import date
            current_year = date.today().year

        if results is None:
            results = self.run_steady_state(save_plot=False)

        flows = results.get('flows', {})
        pipe_scores = []

        for pid in self.wn.pipe_name_list:
            cond = self._pipe_conditions.get(pid, {})
            pipe = self.wn.get_link(pid)

            # Age score (0-100): assume 100-year design life
            install_year = cond.get('install_year')
            if install_year:
                age = current_year - install_year
                age_score = min(100, (age / 100) * 100)
            else:
                age_score = 50  # unknown age = medium risk

            # Condition score (0-100): 1=new(0), 5=failed(100)
            cs = cond.get('condition_score')
            if cs is not None:
                condition_norm = (cs - 1) / 4 * 100
            else:
                condition_norm = 50  # unknown = medium risk

            # Break score (0-100): 5+ breaks = max score
            breaks = cond.get('break_history', 0)
            break_score = min(100, breaks * 20)

            # Hydraulic score (0-100): based on velocity ratio to max
            fdata = flows.get(pid, {})
            v_max = fdata.get('max_velocity_ms', 0)
            # Penalise both high velocity (>2.0 m/s) and very low (<0.3 m/s)
            if v_max > self.DEFAULTS['max_velocity_ms']:
                hydraulic_score = min(100, (v_max / self.DEFAULTS['max_velocity_ms']) * 80)
            elif v_max < 0.3 and v_max > 0:
                hydraulic_score = 60  # stagnation risk
            else:
                hydraulic_score = max(0, (v_max / self.DEFAULTS['max_velocity_ms']) * 30)

            # Weighted priority score — WSAA Asset Management Guidelines
            priority = (age_score * 0.25 + condition_norm * 0.30
                       + break_score * 0.25 + hydraulic_score * 0.20)

            # Risk category
            if priority >= 75:
                risk = 'CRITICAL'
            elif priority >= 50:
                risk = 'HIGH'
            elif priority >= 25:
                risk = 'MEDIUM'
            else:
                risk = 'LOW'

            pipe_scores.append({
                'pipe_id': pid,
                'diameter_mm': int(pipe.diameter * 1000),
                'length_m': round(pipe.length, 1),
                'material': cond.get('material', 'Unknown'),
                'install_year': install_year,
                'age_years': current_year - install_year if install_year else None,
                'condition_score': cs,
                'break_history': breaks,
                'velocity_ms': round(v_max, 2),
                'priority_score': round(priority, 1),
                'risk_category': risk,
                'age_component': round(age_score, 1),
                'condition_component': round(condition_norm, 1),
                'break_component': round(break_score, 1),
                'hydraulic_component': round(hydraulic_score, 1),
            })

        # Sort by priority (highest first)
        pipe_scores.sort(key=lambda x: x['priority_score'], reverse=True)
        return pipe_scores

    # =========================================================================
    # ASSET DETERIORATION MODELLING (J9)
    # =========================================================================

    def predict_deterioration(self, pipe_id, current_year=None, forecast_years=None):
        """
        Predict pipe condition score at future years using Gompertz model.

        Condition score progression:
        C(t) = C_max × exp(-b × exp(-k × age))

        where C_max=5 (failure), b and k depend on material.

        Parameters
        ----------
        pipe_id : str
            Pipe ID with condition data set via set_pipe_condition()
        current_year : int or None
        forecast_years : list of int or None

        Returns dict {year: {'condition_score', 'remaining_life_years'}}.
        Ref: IPWEA Practice Note 7, Gompertz deterioration model
        """
        if not hasattr(self, '_pipe_conditions'):
            self._pipe_conditions = {}

        cond = self._pipe_conditions.get(pipe_id)
        if cond is None:
            return {'error': f'No condition data for {pipe_id}'}

        if current_year is None:
            from datetime import date
            current_year = date.today().year
        if forecast_years is None:
            forecast_years = [current_year + 5, current_year + 10, current_year + 20]

        install_year = cond.get('install_year', current_year - 30)
        current_age = current_year - install_year
        current_cs = cond.get('condition_score', 2.5)

        # Material-specific Gompertz parameters
        # Ref: IPWEA Practice Note 7 Table 4.1
        import math
        MATERIAL_PARAMS = {
            'CI': {'b': 4.0, 'k': 0.04},   # Cast iron (fast deterioration)
            'DI': {'b': 5.0, 'k': 0.03},   # Ductile iron
            'AC': {'b': 3.5, 'k': 0.05},   # Asbestos cement (fast)
            'PVC': {'b': 6.0, 'k': 0.02},  # PVC (slow deterioration)
            'PE': {'b': 6.0, 'k': 0.02},   # PE (slow)
            'Concrete': {'b': 5.0, 'k': 0.025},
        }

        material = cond.get('material', 'DI')
        params = MATERIAL_PARAMS.get(material, {'b': 5.0, 'k': 0.03})
        b, k = params['b'], params['k']

        # Calibrate b to match current condition score
        # C(age) = 5 × exp(-b × exp(-k × age))
        # b_calibrated so that C(current_age) = current_cs
        if current_cs > 0 and current_cs < 5:
            try:
                b_cal = -math.log(current_cs / 5) / math.exp(-k * current_age)
                b = max(1, min(10, b_cal))
            except (ValueError, ZeroDivisionError):
                pass

        results = {}
        for year in forecast_years:
            age = year - install_year
            # Gompertz: C(age) = 5 × exp(-b × exp(-k × age))
            cs = 5.0 * math.exp(-b * math.exp(-k * max(0, age)))
            cs = max(current_cs, min(5.0, cs))  # can't improve over time

            # Estimate remaining life (when cs reaches 5.0)
            remaining = 0
            for future_age in range(int(age), int(age) + 200):
                cs_future = 5.0 * math.exp(-b * math.exp(-k * future_age))
                if cs_future >= 4.9:
                    remaining = future_age - age
                    break

            results[year] = {
                'age_years': age,
                'condition_score': round(cs, 2),
                'remaining_life_years': remaining,
            }

        return results

    # =========================================================================
    # PIPE COST DATABASE MANAGEMENT (J12)
    # =========================================================================

    def set_pipe_cost(self, dn_mm, cost_per_m):
        """Set or update pipe cost for a given DN (mm)."""
        self.PIPE_COST_PER_M[dn_mm] = cost_per_m

    def get_pipe_cost(self, dn_mm):
        """Get pipe cost per metre for a given DN."""
        return self.PIPE_COST_PER_M.get(dn_mm, 0)

    def import_pipe_costs_csv(self, csv_path):
        """Import pipe costs from CSV (columns: dn_mm, cost_per_m)."""
        import csv as csv_mod
        count = 0
        with open(csv_path, 'r') as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                dn = int(row.get('dn_mm', 0))
                cost = float(row.get('cost_per_m', 0))
                if dn > 0 and cost > 0:
                    self.PIPE_COST_PER_M[dn] = cost
                    count += 1
        return count

    # =========================================================================
    # FIELD DATA TEMPLATE (N7)
    # =========================================================================

    def generate_field_template(self, output_path):
        """
        Generate a pre-filled Excel template for field data collection.

        Sheets:
        - Nodes: all junction IDs, space for measured pressure
        - Pipes: all pipe IDs, space for condition/age/breaks
        - Hydrants: fire flow test template

        Parameters
        ----------
        output_path : str
            Path to save the .xlsx file

        Returns dict with template path and element counts.
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        try:
            import pandas as pd
        except ImportError:
            return {'error': 'pandas required (pip install pandas openpyxl)'}

        # Nodes sheet
        node_rows = []
        for jid in self.wn.junction_name_list:
            node = self.wn.get_node(jid)
            node_rows.append({
                'node_id': jid,
                'elevation_m': round(node.elevation, 1),
                'model_demand_lps': round(
                    node.demand_timeseries_list[0].base_value * 1000
                    if node.demand_timeseries_list else 0, 2),
                'measured_pressure_m': '',
                'measurement_date': '',
                'measurement_time': '',
                'notes': '',
            })
        nodes_df = pd.DataFrame(node_rows)

        # Pipes sheet
        pipe_rows = []
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            pipe_rows.append({
                'pipe_id': pid,
                'start_node': pipe.start_node_name,
                'end_node': pipe.end_node_name,
                'diameter_mm': int(pipe.diameter * 1000),
                'length_m': round(pipe.length, 1),
                'roughness_C': pipe.roughness,
                'install_year': '',
                'material': '',
                'condition_score_1to5': '',
                'break_count': '',
                'notes': '',
            })
        pipes_df = pd.DataFrame(pipe_rows)

        # Hydrants sheet
        hydrant_rows = []
        for jid in self.wn.junction_name_list:
            hydrant_rows.append({
                'hydrant_id': jid,
                'static_pressure_m': '',
                'test_flow_lps': '',
                'residual_pressure_m': '',
                'test_date': '',
                'tested_by': '',
            })
        hydrants_df = pd.DataFrame(hydrant_rows)

        with pd.ExcelWriter(output_path) as writer:
            nodes_df.to_excel(writer, sheet_name='Nodes', index=False)
            pipes_df.to_excel(writer, sheet_name='Pipes', index=False)
            hydrants_df.to_excel(writer, sheet_name='Hydrants', index=False)

        return {
            'template_path': output_path,
            'junctions': len(node_rows),
            'pipes': len(pipe_rows),
            'hydrants': len(hydrant_rows),
        }

    # =========================================================================
    # EXCEL NETWORK IMPORT (N5)
    # =========================================================================

    def import_from_excel(self, excel_path):
        """
        Import network from Excel spreadsheet.

        Expected sheets:
        - "Nodes": columns node_id, x, y, elevation, demand_lps
        - "Pipes": columns pipe_id, start_node, end_node, diameter_mm,
                   material, length_m, roughness_C

        Parameters
        ----------
        excel_path : str
            Path to .xlsx file

        Returns dict with import summary and any validation warnings.
        """
        if not os.path.exists(excel_path):
            return {'error': f'File not found: {excel_path}'}

        try:
            import pandas as pd
        except ImportError:
            return {'error': 'pandas required for Excel import (pip install pandas openpyxl)'}

        warnings = []

        try:
            xls = pd.ExcelFile(excel_path)
        except Exception as e:
            return {'error': f'Could not read Excel file: {e}'}

        # Read Nodes sheet
        if 'Nodes' not in xls.sheet_names:
            return {'error': 'Excel file must have a "Nodes" sheet'}
        nodes_df = pd.read_excel(xls, 'Nodes')

        required_node_cols = {'node_id', 'x', 'y', 'elevation'}
        if not required_node_cols.issubset(set(nodes_df.columns)):
            missing = required_node_cols - set(nodes_df.columns)
            return {'error': f'Nodes sheet missing columns: {missing}'}

        # Read Pipes sheet
        if 'Pipes' not in xls.sheet_names:
            return {'error': 'Excel file must have a "Pipes" sheet'}
        pipes_df = pd.read_excel(xls, 'Pipes')

        required_pipe_cols = {'pipe_id', 'start_node', 'end_node', 'diameter_mm', 'length_m'}
        if not required_pipe_cols.issubset(set(pipes_df.columns)):
            missing = required_pipe_cols - set(pipes_df.columns)
            return {'error': f'Pipes sheet missing columns: {missing}'}

        # Validate data
        node_ids = set(nodes_df['node_id'].astype(str))
        pipe_ids = set(pipes_df['pipe_id'].astype(str))

        # Check for duplicates
        if len(node_ids) < len(nodes_df):
            warnings.append('Duplicate node IDs detected — only first occurrence kept')
        if len(pipe_ids) < len(pipes_df):
            warnings.append('Duplicate pipe IDs detected — only first occurrence kept')

        # Check pipe endpoints reference valid nodes
        for _, row in pipes_df.iterrows():
            sn = str(row['start_node'])
            en = str(row['end_node'])
            if sn not in node_ids:
                warnings.append(f'Pipe {row["pipe_id"]}: start_node {sn} not in Nodes sheet')
            if en not in node_ids:
                warnings.append(f'Pipe {row["pipe_id"]}: end_node {en} not in Nodes sheet')

        # Separate reservoirs (nodes with demand_lps == -1 or NaN and high head)
        # Simple heuristic: node with no demand and name starting with R → reservoir
        junctions = []
        reservoirs = []
        for _, row in nodes_df.iterrows():
            nid = str(row['node_id'])
            demand_lps = float(row.get('demand_lps', 0) or 0)
            elev = float(row['elevation'])
            x = float(row['x'])
            y = float(row['y'])

            if nid.upper().startswith('R') and demand_lps <= 0:
                reservoirs.append({
                    'id': nid, 'head': elev, 'x': x, 'y': y,
                })
            else:
                junctions.append({
                    'id': nid, 'elevation': elev,
                    'demand': demand_lps / 1000,  # LPS to m³/s
                    'x': x, 'y': y,
                })

        # If no reservoirs found, treat the node with highest elevation as reservoir
        if not reservoirs and junctions:
            junctions.sort(key=lambda j: j['elevation'], reverse=True)
            r = junctions.pop(0)
            reservoirs.append({
                'id': r['id'], 'head': r['elevation'], 'x': r['x'], 'y': r['y'],
            })
            warnings.append(f'No reservoir detected — using highest node {r["id"]} as reservoir')

        # Build pipes
        pipes = []
        for _, row in pipes_df.iterrows():
            pid = str(row['pipe_id'])
            dn_mm = float(row['diameter_mm'])
            length = float(row['length_m'])
            roughness = float(row.get('roughness_C', 130) or 130)

            pipes.append({
                'id': pid,
                'start': str(row['start_node']),
                'end': str(row['end_node']),
                'diameter': dn_mm,
                'length': length,
                'roughness': roughness,
            })

        # Filter out pipes with invalid node references
        valid_node_ids = {j['id'] for j in junctions} | {r['id'] for r in reservoirs}
        valid_pipes = []
        for p in pipes:
            if p['start'] in valid_node_ids and p['end'] in valid_node_ids:
                valid_pipes.append(p)
            else:
                warnings.append(f'Pipe {p["id"]} skipped — endpoint not in valid nodes')

        # Create network
        name = os.path.splitext(os.path.basename(excel_path))[0]
        self.create_network(
            name=name,
            junctions=junctions,
            reservoirs=reservoirs,
            pipes=valid_pipes,
        )

        return {
            'imported': True,
            'network_name': name,
            'junctions': len(junctions),
            'reservoirs': len(reservoirs),
            'pipes': len(valid_pipes),
            'pipes_skipped': len(pipes) - len(valid_pipes),
            'warnings': warnings,
            'warning_count': len(warnings),
        }

    # =========================================================================
    # LAMONT PIPE BREAK RATE MODEL (O7)
    # =========================================================================

    def lamont_break_forecast(self, forecast_years=None, current_year=2026):
        """
        Forecast pipe break rates using the Lamont (1981) exponential model.

        N(t) = N₀ × exp(A × (t - t₀))

        Where:
          N(t) = breaks per km per year at time t
          N₀ = initial break rate
          A = growth coefficient (material-dependent)
          t - t₀ = pipe age in years

        Material coefficients (breaks/km/yr base, A growth):
        - Cast Iron (CI): N₀=0.15, A=0.055 (fastest deterioration)
        - Asbestos Cement (AC): N₀=0.12, A=0.048
        - Ductile Iron (DI): N₀=0.05, A=0.030
        - Steel: N₀=0.08, A=0.035
        - PVC: N₀=0.02, A=0.015 (slowest)
        - PE: N₀=0.015, A=0.012

        Parameters
        ----------
        forecast_years : list of int or None
            Years to forecast to (default: [2030, 2040, 2050])
        current_year : int
            Current year (default 2026)

        Returns dict with per-pipe break rate forecasts.
        Ref: Lamont P.A. (1981) "Common pipe flow formulas compared with the
             theory of roughness", AWWA Journal 73(5):274-280;
             Shamir & Howard (1979) "An analytic approach to scheduling pipe
             replacement", AWWA Journal 71(5):248-258
        """
        if self.wn is None:
            return {'error': 'No network loaded. Fix: Call api.load_network(path) or api.create_network(...) first.'}

        if forecast_years is None:
            forecast_years = [2030, 2040, 2050]

        # Lamont coefficients by material (infer from roughness C-factor)
        material_params = {
            'CI': {'N0': 0.15, 'A': 0.055, 'label': 'Cast Iron'},
            'AC': {'N0': 0.12, 'A': 0.048, 'label': 'Asbestos Cement'},
            'DI': {'N0': 0.05, 'A': 0.030, 'label': 'Ductile Iron'},
            'Steel': {'N0': 0.08, 'A': 0.035, 'label': 'Steel'},
            'PVC': {'N0': 0.02, 'A': 0.015, 'label': 'PVC'},
            'PE': {'N0': 0.015, 'A': 0.012, 'label': 'PE'},
        }

        def infer_material(C, condition=None):
            """Infer material from Hazen-Williams C-factor."""
            if condition and condition.get('material'):
                mat = condition['material'].upper()
                if mat in material_params:
                    return mat
            # Infer from roughness
            if C < 80:
                return 'CI'
            elif C < 100:
                return 'AC'
            elif C < 130:
                return 'DI'
            elif C < 145:
                return 'Steel'
            else:
                return 'PVC'

        conditions = getattr(self, '_pipe_conditions', {})
        forecasts = []
        total_length_km = 0

        import math

        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            length_km = pipe.length / 1000
            total_length_km += length_km

            cond = conditions.get(pid, {})
            material_code = infer_material(pipe.roughness, cond)
            params = material_params[material_code]

            install_year = cond.get('install_year', 2000)  # default assumption
            age = current_year - install_year
            current_break_rate = params['N0'] * math.exp(params['A'] * age)

            future_rates = {}
            for target_year in forecast_years:
                future_age = target_year - install_year
                rate = params['N0'] * math.exp(params['A'] * future_age)
                expected_breaks = rate * length_km
                # 95% CI: empirical coefficient of variation for Lamont model
                # is typically ±40% (Shamir & Howard 1979, Kleiner & Rajani 2001)
                ci_factor = 0.40
                rate_lower_95 = rate * (1 - 1.96 * ci_factor / 1.96)  # ≈0.6*rate
                rate_upper_95 = rate * (1 + 1.96 * ci_factor / 1.96)  # ≈1.4*rate
                future_rates[target_year] = {
                    'break_rate_per_km_yr': round(rate, 4),
                    'break_rate_lower_95ci': round(max(rate_lower_95, 0), 4),
                    'break_rate_upper_95ci': round(rate_upper_95, 4),
                    'expected_breaks': round(expected_breaks, 2),
                    'expected_breaks_lower_95ci': round(
                        max(rate_lower_95, 0) * length_km, 2),
                    'expected_breaks_upper_95ci': round(
                        rate_upper_95 * length_km, 2),
                    'pipe_age_at_year': future_age,
                }

            forecasts.append({
                'pipe_id': pid,
                'length_m': round(pipe.length, 1),
                'material': params['label'],
                'material_code': material_code,
                'install_year': install_year,
                'current_age': age,
                'current_break_rate_per_km_yr': round(current_break_rate, 4),
                'forecasts': future_rates,
            })

        # Network-wide summary
        total_breaks_by_year = {y: 0 for y in forecast_years}
        for f in forecasts:
            for y, data in f['forecasts'].items():
                total_breaks_by_year[y] += data['expected_breaks']

        # Prioritise pipes with highest future break rate
        forecasts.sort(
            key=lambda f: f['forecasts'][forecast_years[-1]]['break_rate_per_km_yr'],
            reverse=True)

        return {
            'pipe_forecasts': forecasts,
            'network_summary': {
                'total_length_km': round(total_length_km, 2),
                'expected_breaks_by_year': {
                    y: round(v, 1) for y, v in total_breaks_by_year.items()
                },
            },
            'top_10_critical': forecasts[:10],
            'material_coefficients': material_params,
            'confidence_interval_assumption': (
                '95% CI derived from ±40% coefficient of variation typical '
                'for Lamont exponential break models (Kleiner & Rajani 2001, '
                'Urban Water 3:131-150). CI widens with age and small sample '
                'sizes — calibrate locally where data exists.'),
            'caveats': [
                'Exploratory model only. Do NOT use as sole basis for pipe '
                'replacement decisions.',
                'Assumes homogeneous pipe population per material — real '
                'networks have soil-, pressure-, and laying-era variation.',
                'Default install_year=2000 used where no data present — '
                'populate pipe install years via import_pipe_conditions_csv '
                'for defensible results.',
                'Point estimates are MEDIAN of a wide distribution. Treat '
                'the 95% CI as the planning envelope, not the point value.',
            ],
            'reference': 'Lamont (1981) AWWA Journal 73(5); '
                         'Shamir & Howard (1979) AWWA Journal 71(5); '
                         'Kleiner & Rajani (2001) Urban Water 3:131-150',
        }
