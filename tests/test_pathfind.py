"""Stage-1 unit tests for the coarse-A* pathfinder (docs/PATHFINDING_PLAN.md).

Covers the four acceptance cases: an open lane returns straight progress, a boxed-in
Knight routes AROUND a screen, a fully walled-in Knight stays put GRACEFULLY (never
illegal / never None), and the search is DETERMINISTIC under PYTHONHASHSEED=0. The
module is inert at this stage (no caller wired) so these are pure-function tests.
"""
import math

from code.pathfind import find_path

KNIGHT_R = 3.35   # 170mm base radius in inches
INF_R = 0.63      # 32mm infantry base radius


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _screen(x, y0, y1):
    return [(float(x), float(y), INF_R, True) for y in range(y0, y1 + 1)]


def test_open_lane_returns_straight_progress():
    start, goal = (10.0, 12.0), (40.0, 12.0)
    occ = [(25.0, 34.0, INF_R, True)]   # far off the y=12 line, blocks nothing
    p = find_path(start, goal, 12.0, KNIGHT_R, occ)
    assert p is not None
    assert _d(p, goal) < _d(start, goal)        # made progress toward goal
    assert _d(p, start) <= 12.0 + 1e-6          # within the move allowance
    assert abs(p[1] - 12.0) < 4.0               # stayed roughly on the lane


def test_boxed_knight_routes_around_screen():
    start, goal = (10.0, 12.0), (44.0, 12.0)
    occ = _screen(22, 4, 20) + [(30.0, 6.0, 2.0, True), (30.0, 18.0, 2.0, True)]
    p = find_path(start, goal, 12.0, KNIGHT_R, occ)
    assert p is not None
    assert _d(p, goal) < _d(start, goal)        # not stuck at start
    assert _d(p, start) > 1.0                   # actually moved
    # the returned point must not sit inside a blocker's config-space disc
    for ox, oy, orad, _e in occ:
        assert _d(p, (ox, oy)) >= orad + KNIGHT_R - 1.5   # ~half a cell tolerance


def test_walled_in_knight_stays_put_gracefully():
    start, goal = (10.0, 12.0), (40.0, 12.0)
    occ = []
    for deg in range(0, 360, 20):
        a = math.radians(deg)
        occ.append((10.0 + 5.0 * math.cos(a), 12.0 + 5.0 * math.sin(a), 1.5, True))
    p = find_path(start, goal, 12.0, KNIGHT_R, occ)
    assert p is not None                        # never None / never illegal
    assert _d(p, start) < 6.0                   # cannot break the ring → minimal move


def test_determinism():
    start, goal = (10.0, 12.0), (44.0, 12.0)
    occ = _screen(22, 4, 20) + [(30.0, 6.0, 2.0, True), (30.0, 18.0, 2.0, True)]
    a = find_path(start, goal, 12.0, KNIGHT_R, occ)
    b = find_path(start, goal, 12.0, KNIGHT_R, occ)
    assert a == b


def test_no_obstacles_clamps_straight():
    # empty occupants + no walls → straight clamp toward goal (caller-shouldn't-call,
    # but the function must still behave).
    start, goal = (0.0, 0.0), (100.0, 0.0)
    p = find_path(start, goal, 12.0, KNIGHT_R, [])
    assert _d(p, start) == 12.0 or abs(_d(p, start) - 12.0) < 1e-6
