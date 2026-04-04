"""Topology mixin: skeletonisation and network topology analysis."""
import os


class TopologyMixin:

    # =========================================================================
    # NETWORK SKELETONISATION
    # =========================================================================

    def skeletonise(self, min_diameter_mm=100, remove_dead_ends=True,
                    merge_series=True):
        """
        Simplify the network by removing insignificant elements.

        Operations:
        1. Remove dead-end branches below min_diameter_mm
        2. Merge series pipes (two pipes with a junction that has no demand)
        3. Report before/after counts

        Returns dict with 'removed_pipes', 'removed_nodes', 'merged_pipes',
        'before', 'after' counts. Does NOT modify the network — returns
        a plan that the user can review before applying.

        Ref: Walski (2001) "Pipe Network Simplification"
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        before = {
            'nodes': len(self.wn.junction_name_list),
            'pipes': len(self.wn.pipe_name_list),
        }

        dead_end_removals = []
        series_merges = []

        if remove_dead_ends:
            # Find dead-end junctions (degree 1, below diameter threshold)
            for jid in list(self.wn.junction_name_list):
                connected_pipes = []
                for pid in self.wn.pipe_name_list:
                    pipe = self.wn.get_link(pid)
                    if pipe.start_node_name == jid or pipe.end_node_name == jid:
                        connected_pipes.append(pid)
                if len(connected_pipes) == 1:
                    pipe = self.wn.get_link(connected_pipes[0])
                    dn_mm = int(pipe.diameter * 1000)
                    if dn_mm < min_diameter_mm:
                        dead_end_removals.append({
                            'node': jid,
                            'pipe': connected_pipes[0],
                            'diameter_mm': dn_mm,
                        })

        if merge_series:
            # Find series junctions (degree 2, no demand)
            for jid in list(self.wn.junction_name_list):
                # Skip if already marked for removal
                if any(d['node'] == jid for d in dead_end_removals):
                    continue
                # Check demand
                junc = self.wn.get_node(jid)
                demand = 0
                if junc.demand_timeseries_list:
                    demand = abs(junc.demand_timeseries_list[0].base_value)
                if demand > 0.0001:
                    continue  # has demand — can't remove

                connected_pipes = []
                for pid in self.wn.pipe_name_list:
                    pipe = self.wn.get_link(pid)
                    if pipe.start_node_name == jid or pipe.end_node_name == jid:
                        connected_pipes.append(pid)
                if len(connected_pipes) == 2:
                    p1 = self.wn.get_link(connected_pipes[0])
                    p2 = self.wn.get_link(connected_pipes[1])
                    # Equivalent pipe: same diameter (larger), combined length, average roughness
                    eq_length = p1.length + p2.length
                    eq_diameter = max(p1.diameter, p2.diameter)
                    eq_roughness = (p1.roughness + p2.roughness) / 2
                    series_merges.append({
                        'node': jid,
                        'pipe1': connected_pipes[0],
                        'pipe2': connected_pipes[1],
                        'equivalent_length_m': round(eq_length, 1),
                        'equivalent_diameter_mm': int(eq_diameter * 1000),
                        'equivalent_roughness': round(eq_roughness, 0),
                    })

        after = {
            'nodes': before['nodes'] - len(dead_end_removals) - len(series_merges),
            'pipes': before['pipes'] - len(dead_end_removals) - len(series_merges),
        }

        return {
            'dead_end_removals': dead_end_removals,
            'series_merges': series_merges,
            'before': before,
            'after': after,
            'reduction_pct': round(
                (1 - after['pipes'] / max(before['pipes'], 1)) * 100, 1),
        }

    # =========================================================================
    # NETWORK TOPOLOGY ANALYSIS (L3)
    # =========================================================================

    def analyse_topology(self):
        """
        Analyse network topology: dead ends, loops, bridges, connectivity.

        Uses graph theory to identify structural characteristics that
        affect hydraulic reliability and maintenance.

        Returns dict with:
        - dead_ends: list of terminal nodes (degree 1)
        - bridges: pipes whose removal disconnects the network
        - loops: count of independent loops (cyclomatic complexity)
        - connectivity: overall connectivity metrics
        - isolated_segments: groups of nodes not connected to sources

        Ref: Graph theory for water distribution, Todini & Pilati (1988)
        """
        if self.wn is None:
            return {'error': 'No network loaded'}

        # Build adjacency from pipe connections
        adj = {}  # node -> set of (neighbor, pipe_id)
        for pid in self.wn.pipe_name_list:
            pipe = self.wn.get_link(pid)
            sn = pipe.start_node_name
            en = pipe.end_node_name
            adj.setdefault(sn, set()).add((en, pid))
            adj.setdefault(en, set()).add((sn, pid))

        all_nodes = set(self.wn.node_name_list)
        for n in all_nodes:
            adj.setdefault(n, set())

        # Dead ends: nodes with exactly 1 connection (junctions only)
        dead_ends = []
        for nid in self.wn.junction_name_list:
            if len(adj.get(nid, set())) == 1:
                dead_ends.append(nid)

        # Degree distribution
        degrees = {nid: len(adj.get(nid, set())) for nid in all_nodes}

        # Sources: reservoirs and tanks
        sources = set(self.wn.reservoir_name_list) | set(self.wn.tank_name_list)

        # Connectivity: BFS from each source
        def bfs_reachable(start_nodes):
            visited = set()
            queue = list(start_nodes)
            visited.update(queue)
            while queue:
                node = queue.pop(0)
                for neighbor, _ in adj.get(node, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return visited

        reachable = bfs_reachable(sources)
        isolated = all_nodes - reachable

        # Connected components
        remaining = set(all_nodes)
        components = []
        while remaining:
            start = next(iter(remaining))
            component = bfs_reachable({start})
            components.append(component)
            remaining -= component

        # Bridges: pipes whose removal increases component count
        # Use Tarjan's bridge-finding via DFS
        bridges = []
        n_pipes = len(self.wn.pipe_name_list)
        if n_pipes > 0 and n_pipes < 5000:  # skip for very large networks
            bridges = self._find_bridges(adj, all_nodes)

        # Cyclomatic complexity: M = E - V + C
        # E = edges (pipes), V = vertices (nodes), C = connected components
        n_edges = len(self.wn.pipe_name_list)
        n_vertices = len(all_nodes)
        n_components = len(components)
        loops = n_edges - n_vertices + n_components

        # Average node degree
        avg_degree = sum(degrees.values()) / max(len(degrees), 1)

        return {
            'dead_ends': dead_ends,
            'dead_end_count': len(dead_ends),
            'bridges': bridges,
            'bridge_count': len(bridges),
            'loops': max(loops, 0),
            'connected_components': n_components,
            'isolated_nodes': list(isolated),
            'isolated_count': len(isolated),
            'total_nodes': n_vertices,
            'total_pipes': n_edges,
            'avg_node_degree': round(avg_degree, 2),
            'degree_distribution': {
                deg: sum(1 for d in degrees.values() if d == deg)
                for deg in sorted(set(degrees.values()))
            },
            'sources': list(sources),
            'connectivity_ratio': round(len(reachable) / max(n_vertices, 1), 3),
        }

    def _find_bridges(self, adj, all_nodes):
        """
        Find bridge edges using iterative Tarjan's algorithm.
        A bridge is a pipe whose removal disconnects the graph.

        Returns list of pipe IDs that are bridges.
        """
        bridges = []
        disc = {}
        low = {}
        timer = [0]

        for start in all_nodes:
            if start in disc:
                continue
            # Iterative DFS
            # Stack: (node, parent_pipe, neighbor_iterator, is_entering)
            stack = [(start, None, iter(adj.get(start, set())), True)]
            while stack:
                node, parent_pipe, neighbors, entering = stack[-1]
                if entering:
                    disc[node] = low[node] = timer[0]
                    timer[0] += 1
                    stack[-1] = (node, parent_pipe, neighbors, False)

                found_next = False
                for neighbor, pipe_id in neighbors:
                    if neighbor not in disc:
                        stack.append((neighbor, pipe_id,
                                      iter(adj.get(neighbor, set())), True))
                        found_next = True
                        break
                    elif pipe_id != parent_pipe:
                        low[node] = min(low[node], disc[neighbor])

                if not found_next:
                    stack.pop()
                    if stack:
                        parent_node = stack[-1][0]
                        low[parent_node] = min(low[parent_node], low[node])
                        if low[node] > disc[parent_node] and parent_pipe is not None:
                            bridges.append(parent_pipe)

        return bridges
