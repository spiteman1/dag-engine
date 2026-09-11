"""
core/graph.py - DAG graph algorithms: cycle detection and topological sort.

This module is pure Python with zero framework dependencies. It can be
imported and tested in complete isolation from FastAPI, PostgreSQL, or Redis.

Two algorithms are implemented:
    1. detect_cycles()    -- DFS-based cycle detection
    2. topological_sort() -- Kahn's Algorithm returning parallel execution tiers
"""

from collections import defaultdict, deque


def detect_cycles(tasks: list[dict]) -> bool:
    """
    Detect whether the given task graph contains any cycles using DFS.

    A DAG (Directed Acyclic Graph) by definition must have NO cycles.
    Before saving any DAG to the database, we run this check to ensure
    no task directly or indirectly depends on itself -- which would cause
    an infinite execution loop.

    Args:
        tasks: A list of task dicts, each with 'name' and 'dependencies'
               keys. 'dependencies' is a list of task names that must
               complete before this task can run.

               Example:
               [
                   {"name": "A", "dependencies": []},
                   {"name": "B", "dependencies": ["A"]},
                   {"name": "C", "dependencies": ["B"]},
               ]

    Returns:
        True  -- a cycle was detected (DAG is invalid, reject it)
        False -- no cycle found (DAG is valid, safe to save)

    Algorithm: Depth First Search (DFS) with three-colour marking.
        WHITE (0): node not yet visited
        GREY  (1): node currently being explored (in the DFS call stack)
        BLACK (2): node fully explored, all descendants checked

    A cycle exists if we reach a GREY node during exploration -- it means
    we've found a path that leads back to a node currently on the stack.
    """
    # Build an adjacency list: task_name -> list of task_names it depends on
    graph: dict[str, list[str]] = {task["name"]: task["dependencies"] for task in tasks}

    WHITE, GREY, BLACK = 0, 1, 2
    colour: dict[str, int] = defaultdict(int)  # All nodes start WHITE

    def dfs(node: str) -> bool:
        """Returns True if a cycle is found from this node."""
        colour[node] = GREY  # Mark as currently exploring

        for neighbour in graph.get(node, []):
            if colour[neighbour] == GREY:
                # We found a back edge -- this is a cycle
                return True
            if colour[neighbour] == WHITE:
                # Unexplored -- recurse
                if dfs(neighbour):
                    return True

        colour[node] = BLACK  # Fully explored, no cycle through here
        return False

    # Run DFS from every node to handle disconnected subgraphs
    for task_name in graph:
        if colour[task_name] == WHITE:
            if dfs(task_name):
                return True  # Cycle found

    return False  # No cycles detected


def topological_sort(tasks: list[dict]) -> list[list[str]]:
    """
    Return the task execution order grouped into parallel execution tiers
    using Kahn's Algorithm.

    Tasks within the same tier have no dependencies on each other and can
    run concurrently. Each tier must complete fully before the next begins.

    Args:
        tasks: Same format as detect_cycles(). Assumes no cycles exist
               (call detect_cycles() first).

    Returns:
        A list of tiers, where each tier is a list of task names.

        Example output for a linear chain A -> B -> C:
            [["A"], ["B"], ["C"]]

        Example output with parallelism:
            A -> C
            B -> C
            Result: [["A", "B"], ["C"]]
            (A and B can run in parallel, then C runs after both finish)

    Algorithm: Kahn's Algorithm
        1. Calculate in-degree (number of incoming edges) for each node.
        2. Start with all nodes that have in-degree 0 (no dependencies).
        3. Process tier by tier: for each node in the current tier,
           reduce the in-degree of its dependents by 1.
        4. Nodes whose in-degree drops to 0 join the next tier.
        5. Repeat until all nodes are processed.
    """
    # Build adjacency list (dependents) and calculate in-degree in a single pass.
    # dependents: parent task -> list of downstream tasks waiting on it.
    # in_degree: task name -> count of prerequisite dependencies.
    dependents: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {}

    for task in tasks:
        name = task["name"]
        deps = task["dependencies"]

        # Number of prerequisite tasks that must complete before this task can run
        in_degree[name] = len(deps)

  
        # Map each prerequisite to this downstream task
        for dep in deps:
            dependents[dep].append(name)

    # Tier 0: all tasks with no dependencies (in-degree 0)
    queue: deque[str] = deque(
        task["name"] for task in tasks if in_degree[task["name"]] == 0
    )

    tiers: list[list[str]] = []

    while queue:
        # All nodes currently in the queue form one parallel execution tier
        current_tier = list(queue)
        tiers.append(current_tier)
        queue.clear()

        # For each task in this tier, reduce the in-degree of its dependents
        for task_name in current_tier:
            for dependent in dependents[task_name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    # This task's last dependency just finished -- it's ready
                    queue.append(dependent)

    return tiers
