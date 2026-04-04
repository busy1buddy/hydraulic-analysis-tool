"""
CLI Interface for EPANET Hydraulic Analysis API.
Run: python -m epanet_api steady --inp network.inp
"""

import argparse
import json
from epanet_api import HydraulicAPI

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='EPANET Hydraulic Analysis API')
    parser.add_argument('command', choices=['steady', 'transient', 'summary', 'joukowsky'],
                       help='Analysis to run')
    parser.add_argument('--inp', required=True, help='EPANET .inp file')
    parser.add_argument('--valve', help='Valve name for transient analysis')
    parser.add_argument('--closure-time', type=float, default=0.5,
                       help='Valve closure time (seconds)')
    parser.add_argument('--wave-speed', type=float, default=1100,
                       help='Wave speed (m/s) — AS 2280 default 1100 for ductile iron')
    parser.add_argument('--duration', type=float, default=20,
                       help='Transient simulation duration (seconds)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()
    api = HydraulicAPI()

    if args.command == 'summary':
        result = api.load_network(args.inp)
    elif args.command == 'steady':
        api.load_network(args.inp)
        result = api.run_steady_state()
    elif args.command == 'transient':
        if not args.valve:
            parser.error('--valve is required for transient analysis')
        api.load_network(args.inp)
        result = api.run_transient(args.valve,
                                  closure_time=args.closure_time,
                                  wave_speed=args.wave_speed,
                                  sim_duration=args.duration)
    elif args.command == 'joukowsky':
        result = api.joukowsky(args.wave_speed, 1.0)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
