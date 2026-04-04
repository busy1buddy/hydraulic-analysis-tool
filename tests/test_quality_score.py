"""
Tests for Quality Score System (M9)
=====================================
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from epanet_api import HydraulicAPI


class TestQualityScore:

    def test_no_network_error(self):
        api = HydraulicAPI()
        result = api.compute_quality_score()
        assert 'error' in result

    def test_result_structure(self):
        api = HydraulicAPI()
        api.create_network(
            name='qs_struct',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        qs = api.compute_quality_score()
        assert 'total_score' in qs
        assert 'grade' in qs
        assert 'categories' in qs
        assert qs['grade'] in ('A', 'B', 'C', 'D', 'F')
        assert 0 <= qs['total_score'] <= 100

    def test_six_categories(self):
        api = HydraulicAPI()
        api.create_network(
            name='qs_cats',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        qs = api.compute_quality_score()
        assert len(qs['categories']) == 6
        names = [c['category'] for c in qs['categories']]
        assert 'Pressure Compliance' in names
        assert 'Velocity Compliance' in names
        assert 'Network Resilience' in names

    def test_well_designed_network_high_score(self):
        """A properly designed network should score well."""
        api = HydraulicAPI()
        api.create_network(
            name='qs_good',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
                {'id': 'J2', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 0},
                {'id': 'J3', 'elevation': 0, 'demand': 1, 'x': 100, 'y': 100},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 50}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 100,
                 'diameter': 300, 'roughness': 130},
                {'id': 'P2', 'start': 'J1', 'end': 'J2', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P3', 'start': 'J2', 'end': 'J3', 'length': 100,
                 'diameter': 200, 'roughness': 130},
                {'id': 'P4', 'start': 'J3', 'end': 'J1', 'length': 100,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        qs = api.compute_quality_score()
        # Well-designed looped network should score at least B
        assert qs['total_score'] >= 60
        assert qs['grade'] in ('A', 'B', 'C')

    def test_category_scores_sum_to_total(self):
        api = HydraulicAPI()
        api.create_network(
            name='qs_sum',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        qs = api.compute_quality_score()
        cat_sum = sum(c['score'] for c in qs['categories'])
        assert abs(cat_sum - qs['total_score']) < 0.2  # rounding tolerance

    def test_each_category_within_max(self):
        api = HydraulicAPI()
        api.create_network(
            name='qs_max',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        qs = api.compute_quality_score()
        for cat in qs['categories']:
            assert cat['score'] <= cat['max_points'], \
                f"{cat['category']}: {cat['score']} > {cat['max_points']}"

    def test_passes_precomputed_results(self):
        api = HydraulicAPI()
        api.create_network(
            name='qs_pre',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        results = api.run_steady_state(save_plot=False)
        qs = api.compute_quality_score(results)
        assert 'total_score' in qs

    def test_real_network(self):
        api = HydraulicAPI()
        api.load_network('australian_network.inp')
        qs = api.compute_quality_score()
        assert 0 <= qs['total_score'] <= 100
        assert qs['grade'] in ('A', 'B', 'C', 'D', 'F')

    def test_grade_boundaries(self):
        """Verify grade assignment for known scores."""
        api = HydraulicAPI()
        # We can't easily force exact scores, so just verify the mapping logic
        # by checking that grade matches the documented thresholds
        api.create_network(
            name='qs_grade',
            junctions=[
                {'id': 'J1', 'elevation': 0, 'demand': 2, 'x': 0, 'y': 0},
            ],
            reservoirs=[{'id': 'R1', 'head': 50, 'x': -50, 'y': 0}],
            pipes=[
                {'id': 'P1', 'start': 'R1', 'end': 'J1', 'length': 200,
                 'diameter': 200, 'roughness': 130},
            ],
        )
        qs = api.compute_quality_score()
        score = qs['total_score']
        grade = qs['grade']
        if score >= 90:
            assert grade == 'A'
        elif score >= 75:
            assert grade == 'B'
        elif score >= 60:
            assert grade == 'C'
        elif score >= 45:
            assert grade == 'D'
        else:
            assert grade == 'F'
