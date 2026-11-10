#!/usr/bin/env python3
"""RAISE: Room Arrangement for Inclusive and Supportive Environments.

A small, inspectable constraint-satisfaction room planner. One grid cell is one
foot. This is a classroom prototype and research artifact, NOT an ADA,
architectural, medical, or safety certification; a passed check means only that
the encoded rule holds in the model.

This file contains the same solver as the Colab notebook (raise_room_planner.ipynb)
plus a command-line interface.

Examples
--------
    python raise_solver.py presets
    python raise_solver.py solve --preset mobility_bedroom --mode best
    python raise_solver.py solve --preset combined_room --mode mrv --plot layout.png
    python raise_solver.py solve --width 12 --height 10 --doors "4,0;5,0;6,0" \\
        --windows "11,4" --furniture bed,desk,chair,storage --profile mobility
    python raise_solver.py compare --preset sensory_room
    python raise_solver.py baseline --seeds 30

Exit status: 0 solved, 1 no solution or search limit reached, 2 invalid input.
Requires Python 3.10+. Matplotlib is needed only for --plot.
"""

from dataclasses import dataclass, field
from collections import deque
import random
from time import perf_counter
from typing import FrozenSet


Cell = tuple[int, int]


@dataclass(frozen=True)
class Furniture:
    name: str
    label: str
    width: int
    height: int
    color: str
    tags: FrozenSet[str] = frozenset()
    rotatable: bool = True


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    orientation: int = 0


@dataclass(frozen=True)
class AccessibilityProfile:
    name: str
    require_turning_space: bool = False
    require_essential_reach: bool = True
    require_tactile_reach: bool = False
    require_sensory_separation: bool = False
    sensory_distance: int = 3
    route_width: int = 1


@dataclass(frozen=True)
class RoomProblem:
    width: int
    height: int
    doors: tuple[Cell, ...]
    windows: tuple[Cell, ...] = ()
    furniture: tuple[str, ...] = ()
    profile: AccessibilityProfile = field(
        default_factory=lambda: AccessibilityProfile("standard")
    )


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    problem: RoomProblem


def oriented_size(item: Furniture, orientation: int) -> tuple[int, int]:
    """Return width and height after a 0° or 90° rotation."""
    if orientation not in (0, 90):
        raise ValueError("orientation must be 0 or 90 degrees")
    if orientation == 90:
        return item.height, item.width
    return item.width, item.height


FURNITURE_CATALOG = {
    "bed": Furniture("bed", "Bed", 2, 3, "#4C78A8", frozenset({"essential"})),
    "desk": Furniture("desk", "Desk", 2, 1, "#F58518", frozenset({"essential", "noisy"})),
    "chair": Furniture("chair", "Chair", 1, 1, "#54A24B", frozenset({"essential"}), False),
    "storage": Furniture("storage", "Storage", 1, 2, "#B279A2", frozenset({"essential"})),
    "tactile_station": Furniture("tactile_station", "Braille / Tactile Station", 1, 1, "#E45756", frozenset({"essential", "tactile"}), False),
    "quiet_corner": Furniture("quiet_corner", "Quiet Sensory Corner", 2, 2, "#72B7B2", frozenset({"essential", "quiet"}), False),
    "sensory_equipment": Furniture("sensory_equipment", "Sensory Equipment", 1, 1, "#FF9DA6", frozenset({"noisy"}), False),
}


MOBILITY = AccessibilityProfile("Wheelchair / limited mobility", require_turning_space=True, route_width=3)
SENSORY = AccessibilityProfile("Sensory-friendly", require_sensory_separation=True)
COMBINED = AccessibilityProfile(
    "Combined accessibility",
    require_turning_space=True,
    require_tactile_reach=True,
    require_sensory_separation=True,
    route_width=3,
)


PRESETS = {
    "mobility_bedroom": Preset(
        "Wheelchair-accessible bedroom",
        "A bedroom with a three-foot entrance, connected route, and reserved 5×5-foot turning square.",
        RoomProblem(12, 10, ((4, 0), (5, 0), (6, 0)), ((11, 4),),
                    ("bed", "desk", "chair", "storage"), MOBILITY),
    ),
    "sensory_room": Preset(
        "Sensory-friendly room",
        "Separates a quiet corner from noisy or stimulating equipment.",
        RoomProblem(10, 8, ((0, 2), (0, 3), (0, 4)), ((5, 7),),
                    ("desk", "chair", "quiet_corner", "sensory_equipment"), SENSORY),
    ),
    "combined_room": Preset(
        "Combined-accessibility room",
        "Combines mobility, tactile, and sensory constraints.",
        RoomProblem(13, 11, ((5, 0), (6, 0), (7, 0)), ((12, 5),),
                    ("bed", "desk", "chair", "storage", "tactile_station",
                     "quiet_corner", "sensory_equipment"), COMBINED),
    ),
    "impossible_room": Preset(
        "Impossible-room test",
        "A deliberately crowded room whose first furniture domain is empty after fixed-feature filtering.",
        RoomProblem(3, 3, ((0, 0), (1, 0), (2, 0)), (),
                    ("bed", "desk", "storage", "quiet_corner"), COMBINED),
    ),
}


def _on_edge(problem: RoomProblem, cell: Cell) -> bool:
    x, y = cell
    return (0 <= x < problem.width and 0 <= y < problem.height and
            (x in (0, problem.width - 1) or y in (0, problem.height - 1)))


def door_entry_cells(problem: RoomProblem) -> set[Cell]:
    """Return the interior cells immediately beside each edge door."""
    entries: set[Cell] = set()
    for x, y in problem.doors:
        candidates = []
        if x == 0:
            candidates.append((x + 1, y))
        if x == problem.width - 1:
            candidates.append((x - 1, y))
        if y == 0:
            candidates.append((x, y + 1))
        if y == problem.height - 1:
            candidates.append((x, y - 1))
        entries.update(c for c in candidates if 0 <= c[0] < problem.width and 0 <= c[1] < problem.height)
    return entries


def _has_contiguous_edge_run(problem: RoomProblem, cells: tuple[Cell, ...], length: int) -> bool:
    """Return whether an edge contains the requested consecutive opening length."""
    for y in (0, problem.height - 1):
        values = {x for x, cell_y in cells if cell_y == y}
        if any(set(range(start, start + length)) <= values
               for start in range(problem.width - length + 1)):
            return True
    for x in (0, problem.width - 1):
        values = {y for cell_x, y in cells if cell_x == x}
        if any(set(range(start, start + length)) <= values
               for start in range(problem.height - length + 1)):
            return True
    return False


def validate_problem(problem: RoomProblem) -> list[str]:
    """Return readable input errors; an empty list means input is valid."""
    errors: list[str] = []
    if problem.width <= 0 or problem.height <= 0:
        errors.append("Room width and height must be positive.")
        return errors
    if not problem.doors:
        errors.append("Add at least one door on a room edge.")
    for door in problem.doors:
        if not _on_edge(problem, door):
            errors.append(f"Door {door} must be a valid cell on a room edge.")
    if (problem.profile.route_width >= 3 and problem.doors and
            not _has_contiguous_edge_run(problem, problem.doors, problem.profile.route_width)):
        errors.append("Mobility profiles require at least three adjacent door cells on one room edge.")
    for window in problem.windows:
        if not _on_edge(problem, window):
            errors.append(f"Window {window} must be a valid cell on a room edge.")
    if not problem.furniture:
        errors.append("Select at least one furniture item.")
    for name in problem.furniture:
        if name not in FURNITURE_CATALOG:
            errors.append(f"Unknown furniture item: {name}.")
            continue
        item = FURNITURE_CATALOG[name]
        fits = any(w <= problem.width and h <= problem.height for w, h in
                   {oriented_size(item, 0), oriented_size(item, 90) if item.rotatable else oriented_size(item, 0)})
        if not fits:
            errors.append(f"{item.label} is larger than the room.")
    return errors


def occupied_cells(item: Furniture, placement: Placement) -> set[Cell]:
    width, height = oriented_size(item, placement.orientation)
    return {(placement.x + dx, placement.y + dy)
            for dx in range(width) for dy in range(height)}


def placement_is_locally_valid(problem: RoomProblem, assignment: dict[str, Placement],
                               item_name: str, placement: Placement) -> bool:
    """Check boundaries, fixed features, doorway clearance, and overlap."""
    if item_name not in FURNITURE_CATALOG:
        return False
    cells = occupied_cells(FURNITURE_CATALOG[item_name], placement)
    if any(x < 0 or y < 0 or x >= problem.width or y >= problem.height for x, y in cells):
        return False
    forbidden = set(problem.doors) | set(problem.windows) | door_entry_cells(problem)
    if cells & forbidden:
        return False
    for other_name, other_placement in assignment.items():
        if other_name != item_name and cells & occupied_cells(FURNITURE_CATALOG[other_name], other_placement):
            return False
    return True


def generate_domain(problem: RoomProblem, item_name: str) -> list[Placement]:
    """Generate every in-bounds position and permitted orientation."""
    item = FURNITURE_CATALOG[item_name]
    orientations = (0, 90) if item.rotatable and item.width != item.height else (0,)
    values: list[Placement] = []
    for orientation in orientations:
        width, height = oriented_size(item, orientation)
        for y in range(problem.height - height + 1):
            for x in range(problem.width - width + 1):
                values.append(Placement(x, y, orientation))
    return values


def free_cells(problem: RoomProblem, assignment: dict[str, Placement]) -> set[Cell]:
    blocked = set(problem.windows)
    for name, placement in assignment.items():
        blocked |= occupied_cells(FURNITURE_CATALOG[name], placement)
    return {(x, y) for x in range(problem.width) for y in range(problem.height)} - blocked


def reachable_cells(problem: RoomProblem, assignment: dict[str, Placement]) -> set[Cell]:
    """Use BFS over free floor, enforcing profile-specific route clearance."""
    free = free_cells(problem, assignment)
    width = max(1, problem.profile.route_width)
    if width == 1:
        starts = door_entry_cells(problem) & free
        reached = set(starts)
        queue = deque(starts)
        while queue:
            x, y = queue.popleft()
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in free and neighbor not in reached:
                    reached.add(neighbor)
                    queue.append(neighbor)
        return reached

    radius = width // 2

    def footprint(center: Cell) -> set[Cell]:
        x, y = center
        return {(x + dx, y + dy)
                for dx in range(-radius, radius + 1)
                for dy in range(-radius, radius + 1)}

    centers = {
        (x, y)
        for x in range(radius, problem.width - radius)
        for y in range(radius, problem.height - radius)
        if footprint((x, y)) <= free
    }
    doors = set(problem.doors)
    starts = {center for center in centers if len(footprint(center) & doors) >= width}
    reached_centers = set(starts)
    queue = deque(starts)
    while queue:
        x, y = queue.popleft()
        for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbor in centers and neighbor not in reached_centers:
                reached_centers.add(neighbor)
                queue.append(neighbor)
    return set().union(*(footprint(center) for center in reached_centers)) if reached_centers else set()


def _item_is_reachable(name: str, placement: Placement, reached: set[Cell]) -> bool:
    cells = occupied_cells(FURNITURE_CATALOG[name], placement)
    return any((x + dx, y + dy) in reached
               for x, y in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _has_turning_square(problem: RoomProblem, assignment: dict[str, Placement]) -> bool:
    """Reserve a 5×5-foot square that can contain a 60-inch turning circle."""
    free = free_cells(problem, assignment) - set(problem.doors)
    return any({(x + dx, y + dy) for dx in range(5) for dy in range(5)} <= free
               for x in range(problem.width - 4) for y in range(problem.height - 4))


def _sensory_separated(problem: RoomProblem, assignment: dict[str, Placement]) -> bool:
    quiet_cells: set[Cell] = set()
    noisy_cells: set[Cell] = set()
    for name, placement in assignment.items():
        tags = FURNITURE_CATALOG[name].tags
        if "quiet" in tags:
            quiet_cells |= occupied_cells(FURNITURE_CATALOG[name], placement)
        if "noisy" in tags:
            noisy_cells |= occupied_cells(FURNITURE_CATALOG[name], placement)
    if not quiet_cells or not noisy_cells:
        return True
    distance = min(abs(qx - nx) + abs(qy - ny)
                   for qx, qy in quiet_cells for nx, ny in noisy_cells)
    return distance >= problem.profile.sensory_distance


def evaluate_constraints(problem: RoomProblem, assignment: dict[str, Placement]) -> dict[str, bool]:
    """Evaluate enabled accessibility requirements for a complete layout."""
    reached = reachable_cells(problem, assignment)
    entries = door_entry_cells(problem)
    results = {
        "doorway_clear": bool(entries) and entries <= free_cells(problem, assignment),
        "connected_travel_path": bool(reached),
    }
    if problem.profile.require_essential_reach:
        essential = [(name, p) for name, p in assignment.items()
                     if "essential" in FURNITURE_CATALOG[name].tags]
        results["essential_items_reachable"] = all(
            _item_is_reachable(name, p, reached) for name, p in essential
        )
    if problem.profile.require_turning_space:
        results["clear_turning_space"] = _has_turning_square(problem, assignment)
    if problem.profile.require_tactile_reach:
        tactile = [(name, p) for name, p in assignment.items()
                   if "tactile" in FURNITURE_CATALOG[name].tags]
        results["tactile_station_reachable"] = bool(tactile) and all(
            _item_is_reachable(name, p, reached) for name, p in tactile
        )
    if problem.profile.require_sensory_separation:
        results["sensory_zones_separated"] = _sensory_separated(problem, assignment)
    return results


def validate_complete_assignment(problem: RoomProblem, assignment: dict[str, Placement]) -> tuple[bool, dict[str, bool]]:
    """Re-validate local placement and global accessibility rules with the shared constraint functions."""
    complete = set(assignment) == set(problem.furniture)
    local = complete
    built: dict[str, Placement] = {}
    if complete:
        for name in problem.furniture:
            if not placement_is_locally_valid(problem, built, name, assignment[name]):
                local = False
                break
            built[name] = assignment[name]
    results = evaluate_constraints(problem, assignment) if complete else {}
    results = {"all_items_placed": complete, "no_overlap_or_fixed_conflict": local, **results}
    return all(results.values()), results


@dataclass(frozen=True)
class LayoutScore:
    """Explainable quality score for an already-valid room layout."""

    total: float
    breakdown: dict[str, float]


def score_layout(problem: RoomProblem, assignment: dict[str, Placement]) -> LayoutScore:
    """Score practical preferences without replacing accessibility constraints."""
    centers: list[tuple[float, float]] = []
    for name, placement in assignment.items():
        width, height = oriented_size(FURNITURE_CATALOG[name], placement.orientation)
        centers.append((placement.x + width / 2, placement.y + height / 2))

    if len(centers) < 2:
        furniture_spread = 0.0
    else:
        distances = [
            (abs(ax - bx) / problem.width + abs(ay - by) / problem.height) / 2
            for index, (ax, ay) in enumerate(centers)
            for bx, by in centers[index + 1:]
        ]
        furniture_spread = 40 * (sum(distances) / len(distances))

    wall_items = [name for name in assignment if name in {"bed", "storage"}]
    wall_hits = 0
    for name in wall_items:
        cells = occupied_cells(FURNITURE_CATALOG[name], assignment[name])
        if any(x in (0, problem.width - 1) or y in (0, problem.height - 1)
               for x, y in cells):
            wall_hits += 1
    wall_placement = 20 * wall_hits / len(wall_items) if wall_items else 0.0

    desk_near_window = 0.0
    if "desk" in assignment and problem.windows:
        item = FURNITURE_CATALOG["desk"]
        width, height = oriented_size(item, assignment["desk"].orientation)
        desk_center = (assignment["desk"].x + width / 2,
                       assignment["desk"].y + height / 2)
        distance = min(abs(desk_center[0] - x - .5) + abs(desk_center[1] - y - .5)
                       for x, y in problem.windows)
        max_distance = max(1.0, problem.width + problem.height - 2)
        desk_near_window = 20 * max(0.0, 1 - distance / max_distance)

    center_x = set(range(problem.width // 3, problem.width - problem.width // 3))
    center_y = set(range(problem.height // 3, problem.height - problem.height // 3))
    center_cells = {(x, y) for x in center_x for y in center_y}
    occupied: set[Cell] = set()
    for name, placement in assignment.items():
        occupied |= occupied_cells(FURNITURE_CATALOG[name], placement)
    blocked_ratio = len(occupied & center_cells) / len(center_cells) if center_cells else 0.0
    open_center = 20 * (1 - blocked_ratio)

    breakdown = {
        "furniture_spread": round(furniture_spread, 3),
        "wall_placement": round(wall_placement, 3),
        "desk_near_window": round(desk_near_window, 3),
        "open_center": round(open_center, 3),
    }
    return LayoutScore(round(sum(breakdown.values()), 3), breakdown)


@dataclass(frozen=True)
class SolverConfig:
    use_mrv: bool = False
    use_forward_checking: bool = False
    max_attempts: int = 200_000
    candidate_limit: int = 50
    select_best: bool = False
    rank_values_by_score: bool = False
    randomize_values: bool = False
    random_seed: int = 7


@dataclass
class SearchMetrics:
    attempts: int = 0
    backtracks: int = 0
    max_depth: int = 0
    elapsed_seconds: float = 0.0
    valid_candidates: int = 0


@dataclass
class SolveResult:
    status: str
    assignment: dict[str, Placement]
    constraints: dict[str, bool]
    metrics: SearchMetrics
    message: str = ""
    layout_score: LayoutScore | None = None


def solve(problem: RoomProblem, config: SolverConfig = SolverConfig()) -> SolveResult:
    """Solve the furniture CSP with backtracking and optional MRV/forward checking."""
    start = perf_counter()
    metrics = SearchMetrics()
    errors = validate_problem(problem)
    if errors:
        metrics.elapsed_seconds = perf_counter() - start
        return SolveResult("invalid_input", {}, {}, metrics, " ".join(errors))
    rng = random.Random(config.random_seed)
    domains = {
        name: [p for p in generate_domain(problem, name)
               if placement_is_locally_valid(problem, {}, name, p)]
        for name in problem.furniture
    }
    if config.randomize_values:
        for values in domains.values():
            rng.shuffle(values)
    assignment: dict[str, Placement] = {}
    hit_limit = False
    stop_search = False
    collect_best = config.select_best
    best_answer: dict[str, Placement] | None = None
    best_score: LayoutScore | None = None

    def legal_values(name: str) -> list[Placement]:
        values = [p for p in domains[name]
                  if placement_is_locally_valid(problem, assignment, name, p)]
        if config.rank_values_by_score:
            values.sort(key=lambda placement: (
                -score_layout(problem, {**assignment, name: placement}).total,
                placement.y,
                placement.x,
                placement.orientation,
            ))
        return values

    def search() -> dict[str, Placement] | None:
        nonlocal hit_limit, stop_search, best_answer, best_score
        metrics.max_depth = max(metrics.max_depth, len(assignment))
        if len(assignment) == len(problem.furniture):
            if not validate_complete_assignment(problem, assignment)[0]:
                return None
            candidate = dict(assignment)
            candidate_score = score_layout(problem, candidate)
            metrics.valid_candidates += 1
            if best_score is None or candidate_score.total > best_score.total:
                best_answer = candidate
                best_score = candidate_score
            if not collect_best:
                return candidate
            if metrics.valid_candidates >= max(1, config.candidate_limit):
                stop_search = True
            return None
        remaining = [name for name in problem.furniture if name not in assignment]
        if config.use_mrv:
            choices = [(len(legal_values(name)), index, name)
                       for index, name in enumerate(remaining)]
            _, _, name = min(choices)
        else:
            name = remaining[0]
        for placement in legal_values(name):
            if metrics.attempts >= config.max_attempts:
                hit_limit = True
                return None
            metrics.attempts += 1
            assignment[name] = placement
            metrics.max_depth = max(metrics.max_depth, len(assignment))
            viable = True
            if config.use_forward_checking:
                viable = all(legal_values(other) for other in remaining if other != name)
            if viable:
                answer = search()
                if answer is not None:
                    return answer
                if hit_limit or stop_search:
                    assignment.pop(name, None)
                    return None
            assignment.pop(name, None)
        metrics.backtracks += 1
        return None

    answer = search()
    metrics.elapsed_seconds = perf_counter() - start
    if collect_best and best_answer is not None:
        answer = best_answer
    if answer is not None:
        valid, constraints = validate_complete_assignment(problem, answer)
        assert valid
        selected_score = best_score or score_layout(problem, answer)
        if hit_limit:
            message = "Best valid layout found within the search budget."
        elif collect_best:
            message = f"Best layout selected from {metrics.valid_candidates} valid candidates."
        else:
            message = "First valid layout found."
        return SolveResult("solved", answer, constraints, metrics, message, selected_score)
    if hit_limit:
        return SolveResult("limit_reached", {}, {}, metrics,
                           "Search limit reached; this does not prove that no layout exists.")
    return SolveResult("no_solution", {}, {}, metrics,
                       "The search exhausted every arrangement; no valid layout exists.")


def evaluation_conditions(problem: RoomProblem) -> dict[str, SolveResult]:
    """Separate search-efficiency and layout-quality conditions."""
    return {
        "Basic — first valid": solve(problem, SolverConfig()),
        "MRV + FC — first valid": solve(
            problem, SolverConfig(use_mrv=True, use_forward_checking=True)
        ),
        "MRV + FC — best of 50": solve(
            problem,
            SolverConfig(use_mrv=True, use_forward_checking=True, select_best=True,
                         rank_values_by_score=True, candidate_limit=50),
        ),
        "MRV + FC random order — best of 50": solve(
            problem,
            SolverConfig(use_mrv=True, use_forward_checking=True,
                         select_best=True, randomize_values=True,
                         random_seed=7, candidate_limit=50),
        ),
    }


def compare_solvers(problem: RoomProblem) -> tuple[SolveResult, SolveResult]:
    """Compatibility helper for the first-solution efficiency comparison."""
    results = evaluation_conditions(problem)
    return results["Basic — first valid"], results["MRV + FC — first valid"]


CONSTRAINT_LABELS = {
    "all_items_placed": "All requested furniture is placed",
    "no_overlap_or_fixed_conflict": "Furniture does not overlap or block fixed features",
    "doorway_clear": "Doorway and interior entry space are clear",
    "connected_travel_path": "A connected travel corridor with profile-specific clearance starts at the door",
    "essential_items_reachable": "Essential furniture is reachable from the travel path",
    "clear_turning_space": "A clear 5×5-foot square can contain a 60-inch turning circle",
    "tactile_station_reachable": "The Braille / tactile station is reachable",
    "sensory_zones_separated": "Quiet and noisy sensory zones are separated",
}


def constraint_messages(results: dict[str, bool]) -> list[str]:
    return [f"{'✓' if passed else '✗'} {CONSTRAINT_LABELS.get(name, name.replace('_', ' ').title())}"
            for name, passed in results.items()]


def metrics_table(results: dict[str, SolveResult]) -> list[dict[str, object]]:
    rows = []
    for label, result in results.items():
        rows.append({
            "condition": label,
            "status": result.status,
            "attempts": result.metrics.attempts,
            "backtracks": result.metrics.backtracks,
            "valid_candidates": result.metrics.valid_candidates,
            "score": result.layout_score.total if result.layout_score else None,
            "elapsed_seconds": round(result.metrics.elapsed_seconds, 6),
        })
    return rows


def _first_turning_square(problem: RoomProblem, assignment: dict[str, Placement]) -> Cell | None:
    free = free_cells(problem, assignment) - set(problem.doors)
    for y in range(problem.height - 4):
        for x in range(problem.width - 4):
            if {(x + dx, y + dy) for dx in range(5) for dy in range(5)} <= free:
                return x, y
    return None


def plot_layout(problem: RoomProblem, assignment: dict[str, Placement], ax=None):
    """Draw a labeled layout; returns the Matplotlib axis for reuse/testing."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 6))
    reached = reachable_cells(problem, assignment)
    if reached:
        xs, ys = zip(*reached)
        path = ax.scatter([x + .5 for x in xs], [y + .5 for y in ys], s=18,
                          color="#D9EAF7", marker="s", label="Reachable floor", zorder=0)
        path.set_gid("path")
    for x, y in problem.doors:
        patch = Rectangle((x, y), 1, 1, facecolor="#FFFFFF", edgecolor="#0072B2", linewidth=3)
        patch.set_gid("door")
        ax.add_patch(patch)
        ax.text(x + .5, y + .5, "DOOR", ha="center", va="center", fontsize=7, weight="bold")
    for x, y in problem.windows:
        patch = Rectangle((x, y), 1, 1, facecolor="#BDE3FF", edgecolor="#005A8D", hatch="//")
        patch.set_gid("window")
        ax.add_patch(patch)
    turning = _first_turning_square(problem, assignment) if problem.profile.require_turning_space else None
    if turning:
        patch = Rectangle(turning, 5, 5, facecolor="none", edgecolor="#009E73",
                          linewidth=2, linestyle="--")
        patch.set_gid("turning-area")
        ax.add_patch(patch)
        ax.text(turning[0] + 2.5, turning[1] + 2.5, "5×5 TURNING AREA\n60-INCH CIRCLE PROXY",
                ha="center", va="center", color="#006B4E", fontsize=8, weight="bold")
    plot_labels = {
        "tactile_station": "Tactile",
        "quiet_corner": "Quiet Corner",
        "sensory_equipment": "Sens.",
    }
    for name, placement in assignment.items():
        item = FURNITURE_CATALOG[name]
        width, height = oriented_size(item, placement.orientation)
        patch = Rectangle((placement.x, placement.y), width, height,
                          facecolor=item.color, edgecolor="#202124", linewidth=1.5,
                          alpha=.9, label=item.label)
        patch.set_gid("furniture")
        ax.add_patch(patch)
        ax.text(placement.x + width / 2, placement.y + height / 2,
                plot_labels.get(name, item.label), ha="center", va="center",
                fontsize=7.5, color="white", weight="bold", clip_on=True)
    ax.set_xlim(0, problem.width)
    ax.set_ylim(0, problem.height)
    ax.set_aspect("equal")
    ax.set_xticks(range(problem.width + 1))
    ax.set_yticks(range(problem.height + 1))
    ax.grid(True, color="#C7C7C7", linewidth=.6)
    ax.set_xlabel("Width (feet; 1 cell = 1 foot)")
    ax.set_ylabel("Height (feet; 1 cell = 1 foot)")
    ax.set_title(f"Assistive Room Layout — {problem.profile.name}\nClassroom planning model; not ADA certification")
    handles = [Patch(facecolor="#FFFFFF", edgecolor="#0072B2", label="Door"),
               Patch(facecolor="#BDE3FF", edgecolor="#005A8D", hatch="//", label="Window")]
    handles += [Patch(facecolor=FURNITURE_CATALOG[n].color, label=FURNITURE_CATALOG[n].label)
                for n in assignment]
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    return ax


# ----------------------------------------------------------------------------
# Command-line interface
# ----------------------------------------------------------------------------
import argparse
import statistics
import sys

MODES = {
    "basic": ("Basic backtracking, first valid layout", SolverConfig()),
    "mrv": ("MRV + forward checking, first valid layout",
            SolverConfig(use_mrv=True, use_forward_checking=True)),
    "best": ("MRV + forward checking, score-guided best of 50",
             SolverConfig(use_mrv=True, use_forward_checking=True, select_best=True,
                          rank_values_by_score=True, candidate_limit=50)),
}
PROFILES = {"standard": AccessibilityProfile("Standard"), "mobility": MOBILITY,
            "sensory": SENSORY, "combined": COMBINED}
LEGEND = {"bed": "B", "desk": "D", "chair": "C", "storage": "S", "tactile_station": "T",
          "quiet_corner": "Q", "sensory_equipment": "E"}


def parse_cells(text: str, label: str) -> tuple[Cell, ...]:
    """Parse 'x,y;x,y' into a tuple of cells."""
    cells = []
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            x, y = (int(v) for v in part.split(","))
        except ValueError:
            raise ValueError(f"{label} must look like '4,0;5,0' (got {part!r}).") from None
        cells.append((x, y))
    return tuple(cells)


def ascii_layout(problem: RoomProblem, assignment: dict[str, Placement]) -> str:
    """Text drawing: top row is the highest y. # door, W window, . reached floor, , other floor."""
    grid = {(x, y): "," for x in range(problem.width) for y in range(problem.height)}
    for cell in reachable_cells(problem, assignment):
        grid[cell] = "."
    for cell in problem.windows:
        grid[cell] = "W"
    for cell in problem.doors:
        grid[cell] = "#"
    for name, placement in assignment.items():
        for cell in occupied_cells(FURNITURE_CATALOG[name], placement):
            grid[cell] = LEGEND.get(name, "?")
    rows = ["".join(grid[(x, y)] for x in range(problem.width))
            for y in reversed(range(problem.height))]
    key = ", ".join(f"{LEGEND.get(n, '?')}={FURNITURE_CATALOG[n].label}" for n in assignment)
    return "\n".join(rows) + f"\n(# door, W window, . reached floor, , other floor; {key})"


def report(problem: RoomProblem, result: SolveResult) -> None:
    print(f"Status: {result.status}\n{result.message}")
    if result.status == "solved" or result.status == "limit_reached" and result.assignment:
        print("\n" + ascii_layout(problem, result.assignment))
        print("\nConstraint checks:")
        for line in constraint_messages(result.constraints):
            print("  " + line)
        if result.layout_score:
            s = result.layout_score
            print(f"\nPreference score: {s.total:.3f} / 100 (valid layouts only)")
    m = result.metrics
    print(f"\nSearch: {m.attempts:,} attempts, {m.backtracks:,} backtracks, "
          f"{m.valid_candidates} valid candidate(s), max depth {m.max_depth}, "
          f"{m.elapsed_seconds:.2f} s")


def build_problem(args) -> RoomProblem:
    if args.preset:
        if args.preset not in PRESETS:
            raise ValueError(f"Unknown preset {args.preset!r}. Choose from: {', '.join(PRESETS)}.")
        return PRESETS[args.preset].problem
    if args.width is None or args.height is None or not args.doors or not args.furniture:
        raise ValueError("Give --preset, or --width, --height, --doors and --furniture.")
    furniture = tuple(x.strip() for x in args.furniture.split(",") if x.strip())
    return RoomProblem(args.width, args.height, parse_cells(args.doors, "Doors"),
                       parse_cells(args.windows, "Windows"), furniture, PROFILES[args.profile])


def cmd_presets(_args) -> int:
    for key, preset in PRESETS.items():
        p = preset.problem
        print(f"{key}: {p.width} x {p.height} ft, {len(p.furniture)} items, profile '{p.profile.name}'")
        print(f"    {preset.description}")
    return 0


def cmd_solve(args) -> int:
    try:
        problem = build_problem(args)
        errors = validate_problem(problem)
    except (ValueError, KeyError) as error:
        print("Invalid input:", error)
        return 2
    if errors:
        print("Invalid input:")
        for error in errors:
            print("-", error)
        return 2
    label, base = MODES[args.mode]
    config = SolverConfig(**{**base.__dict__, "max_attempts": args.max_attempts})
    print(f"Mode: {label}\n")
    result = solve(problem, config)
    report(problem, result)
    if args.plot and result.assignment:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ax = plot_layout(problem, result.assignment)
        ax.figure.savefig(args.plot, dpi=200, bbox_inches="tight")
        print(f"Saved plot to {args.plot}")
    return 0 if result.status == "solved" else 1


def cmd_compare(args) -> int:
    if args.preset not in PRESETS:
        print(f"Unknown preset {args.preset!r}. Choose from: {', '.join(PRESETS)}.")
        return 2
    problem = PRESETS[args.preset].problem
    print(f"{args.preset}: first-solution comparison and best-of-50 selection\n")
    print(f"{'Condition':36s} {'Status':14s} {'Attempts':>9s} {'Backtracks':>11s} {'Valid':>6s} {'Score':>8s}")
    for label, result in evaluation_conditions(problem).items():
        score = f"{result.layout_score.total:.3f}" if result.layout_score else "-"
        m = result.metrics
        print(f"{label:36s} {result.status:14s} {m.attempts:9,d} {m.backtracks:11,d} {m.valid_candidates:6d} {score:>8s}")
    print("\nNote: the last row shuffles each domain once (single seed); use the 'baseline' "
          "command for the multi-seed random-sampling comparison.")
    return 0


def random_valid_layouts(problem: RoomProblem, rng: random.Random, want: int = 50,
                         max_draws: int = 50_000) -> tuple[list[float], int]:
    """Randomized sequential placement with rejection (not uniform over valid layouts)."""
    domains = {n: [q for q in generate_domain(problem, n)
                   if placement_is_locally_valid(problem, {}, n, q)] for n in problem.furniture}
    scores, seen, draws = [], set(), 0
    while len(scores) < want and draws < max_draws:
        draws += 1
        order = list(problem.furniture)
        rng.shuffle(order)
        layout: dict[str, Placement] = {}
        for name in order:
            legal = [q for q in domains[name] if placement_is_locally_valid(problem, layout, name, q)]
            if not legal:
                break
            layout[name] = rng.choice(legal)
        else:
            if validate_complete_assignment(problem, layout)[0]:
                key = tuple(sorted(layout.items(), key=lambda kv: kv[0]))
                if key not in seen:
                    seen.add(key)
                    scores.append(score_layout(problem, layout).total)
    return scores, draws


def cmd_baseline(args) -> int:
    keys = ["mobility_bedroom", "sensory_room", "combined_room"] if args.preset == "all" else [args.preset]
    if any(k not in PRESETS for k in keys):
        print(f"Unknown preset. Choose from: all, {', '.join(PRESETS)}.")
        return 2
    print(f"{'Room':18s} {'Guided (att.)':>15s} {'Random mean ± SD':>18s} {'Range':>13s} {'Random >= guided':>17s}")
    for key in keys:
        problem = PRESETS[key].problem
        guided = solve(problem, MODES["best"][1])
        if guided.layout_score is None:
            print(f"{key:18s} no valid layout ({guided.status})")
            continue
        best = []
        for seed in range(args.seeds):
            scores, _ = random_valid_layouts(problem, random.Random(seed))
            if len(scores) >= 50:
                best.append(max(scores))
        g = guided.layout_score.total
        sd = statistics.stdev(best) if len(best) > 1 else 0.0
        print(f"{key:18s} {g:9.3f} ({guided.metrics.attempts:3d}) {statistics.mean(best):10.1f} ± {sd:4.1f} "
              f"{min(best):6.1f}-{max(best):5.1f} {sum(b >= g for b in best):9d} / {len(best):<5d}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RAISE room planner (classroom prototype, not an ADA certification).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("presets", help="list the built-in rooms").set_defaults(func=cmd_presets)

    s = sub.add_parser("solve", help="find a layout for a preset or a custom room")
    s.add_argument("--preset", choices=list(PRESETS))
    s.add_argument("--width", type=int)
    s.add_argument("--height", type=int)
    s.add_argument("--doors", help="edge cells, e.g. '4,0;5,0;6,0'")
    s.add_argument("--windows", default="", help="edge cells, e.g. '11,4'")
    s.add_argument("--furniture", help="comma-separated: " + ", ".join(FURNITURE_CATALOG))
    s.add_argument("--profile", choices=list(PROFILES), default="mobility")
    s.add_argument("--mode", choices=list(MODES), default="best")
    s.add_argument("--max-attempts", type=int, default=200_000)
    s.add_argument("--plot", metavar="FILE.png", help="save a Matplotlib drawing")
    s.set_defaults(func=cmd_solve)

    c = sub.add_parser("compare", help="first-solution and best-of-50 comparison for a preset")
    c.add_argument("--preset", required=True, choices=list(PRESETS))
    c.set_defaults(func=cmd_compare)

    b = sub.add_parser("baseline", help="multi-seed random-sampling baseline (paper Table 4)")
    b.add_argument("--preset", default="all")
    b.add_argument("--seeds", type=int, default=30)
    b.set_defaults(func=cmd_baseline)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
