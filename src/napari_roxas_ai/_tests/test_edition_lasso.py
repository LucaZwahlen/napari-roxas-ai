from types import SimpleNamespace

import numpy as np
import pytest

from napari_roxas_ai._edition._tools import (
    LASSO,
    LassoSelectTool,
    LayerTools,
    LineSelectTool,
    SelectionOutline,
    ToolBar,
    shapes_action_states,
    shapes_actions,
    shapes_rows,
)

SQUARE = np.array([[0, 0], [0, 10], [10, 10], [10, 0]], dtype=float)
# A lasso drawn from empty space around the first square
AROUND_FIRST = [(-5, -5), (-5, 15), (15, 15), (15, -5)]


@pytest.fixture
def tools(make_napari_viewer, qtbot):
    viewer = make_napari_viewer()
    layer = viewer.add_shapes([SQUARE, SQUARE + 20], shape_type="polygon")
    lasso = LassoSelectTool(viewer)
    # The lassos hit-tested (a click is not)
    lassos = []
    real_hits = lasso.hits

    def hits(shapes, points):
        lassos.append(points)
        return real_hits(shapes, points)

    lasso.hits = hits
    outline = SelectionOutline.add(viewer, layer)
    toolbar = ToolBar(viewer, shapes_rows([lasso]))
    shapes_tools = LayerTools(
        viewer,
        toolbar,
        custom_tools=[lasso],
        actions=shapes_actions(),
        action_states=shapes_action_states,
    )
    shapes_tools.attach(layer)
    return SimpleNamespace(
        viewer=viewer,
        layer=layer,
        toolbar=toolbar,
        tools=shapes_tools,
        lasso=lasso,
        outline=outline,
        lassos=lassos,
        qtbot=qtbot,
    )


def _settle(qtbot):
    # The active layer is checked once it settled
    qtbot.wait(10)


class FakeMouseEvent:
    def __init__(self, position, modifiers=()):
        self.type = "mouse_press"
        self.button = 1
        self.position = position
        self.modifiers = list(modifiers)


def _press(layer, position, modifiers=()):
    """Press with the lasso's drag callback: (generator or None, event)."""
    event = FakeMouseEvent(position, modifiers)
    drag = layer.mouse_drag_callbacks[0](layer, event)
    try:
        next(drag)
    except StopIteration:
        return None, event
    return drag, event


def _move(drag, event, position):
    event.type = "mouse_move"
    event.position = position
    next(drag)


def _release(drag, event):
    event.type = "mouse_release"
    with pytest.raises(StopIteration):
        next(drag)


def _draw_lasso(layer, points, modifiers=()):
    drag, event = _press(layer, points[0], modifiers)
    assert drag is not None, "the lasso must start (not on the selection)"
    for point in points[1:]:
        _move(drag, event, point)
    _release(drag, event)


def test_lasso_is_napari_select_mode(tools):
    tools.toolbar._buttons[LASSO].click()
    _settle(tools.qtbot)

    assert tools.toolbar.checked == LASSO
    assert tools.layer.mode == "select"
    assert not tools.layer.mouse_pan
    assert tools.layer.cursor == "cross"
    # Runs before napari's select drag
    assert tools.layer.mouse_drag_callbacks[0] == tools.lasso._on_drag
    assert tools.outline.layer in tools.viewer.layers
    assert tools.outline.layer.name == f"[{tools.layer.name}] - overlay"
    # The outline does not take over the active layer
    assert tools.viewer.layers.selection.active is tools.layer

    # Another tool turns the lasso off and restores the layer
    tools.toolbar._buttons["direct"].click()
    assert tools.layer.mode == "direct"
    assert tools.toolbar.checked == "direct"
    assert tools.lasso._on_drag not in tools.layer.mouse_drag_callbacks
    assert tools.layer.cursor != "cross"

    # Turned off by clicking it again: back to pan/zoom
    tools.toolbar._buttons[LASSO].click()
    tools.toolbar._buttons[LASSO].click()
    assert tools.layer.mode == "pan_zoom"
    assert tools.layer.mouse_pan


def test_lasso_without_outline_still_selects(tools):
    tools.outline.remove()
    tools.toolbar._buttons[LASSO].click()
    _draw_lasso(tools.layer, AROUND_FIRST)

    assert tools.layer.selected_data == {0}


def test_lasso_selection_is_napari_selection(tools):
    tools.toolbar._buttons[LASSO].click()
    drag, event = _press(tools.layer, AROUND_FIRST[0])

    # While drawing, napari's select drag is out (no rectangle): pan_zoom
    # mode without panning, the outline is a solid line
    assert tools.lasso.is_drawing
    assert tools.layer.mode == "pan_zoom"
    assert not tools.layer.mouse_pan
    outline = tools.outline.layer
    for point in AROUND_FIRST[1:]:
        _move(drag, event, point)
    # One closed outline through the lasso's points
    assert outline.shape_type == ["polygon"]
    assert len(outline.data[0]) == len(AROUND_FIRST)

    _release(drag, event)

    # Back in napari's select mode with the lassoed shape selected: napari
    # shows, moves and deletes it as with its rectangle selection
    assert not tools.lasso.is_drawing
    assert len(outline.data) == 0
    assert tools.layer.mode == "select"
    assert tools.toolbar.checked == LASSO
    assert tools.layer.cursor == "cross"
    assert tools.layer.selected_data == {0}
    (polygon,) = tools.lassos
    np.testing.assert_allclose(polygon, AROUND_FIRST)


def test_drag_on_a_shape_is_left_to_napari(tools):
    tools.toolbar._buttons[LASSO].click()
    _draw_lasso(tools.layer, AROUND_FIRST)

    # On the selected shape: napari's select drag moves it, no lasso
    drag, _event = _press(tools.layer, (5, 5))
    assert drag is None
    assert not tools.lasso.is_drawing
    assert tools.layer.mode == "select"
    assert len(tools.lassos) == 1


def test_drag_on_an_unselected_shape_draws_a_lasso(tools):
    tools.toolbar._buttons[LASSO].click()
    _draw_lasso(tools.layer, AROUND_FIRST)
    assert tools.layer.selected_data == {0}

    # Starting on the second (unselected) square: a lasso, not napari's
    # select-and-move
    around_second = [(25, 25), (15, 35), (35, 35), (35, 15)]
    _draw_lasso(tools.layer, around_second)
    assert len(tools.lassos) == 2
    assert tools.layer.selected_data == {1}
    assert np.array_equal(tools.layer.data[1], SQUARE + 20)  # not moved


def test_lasso_with_shift_is_additive(tools):
    tools.toolbar._buttons[LASSO].click()
    _draw_lasso(tools.layer, AROUND_FIRST)
    around_second = [(x + 20, y + 20) for x, y in AROUND_FIRST]
    _draw_lasso(tools.layer, around_second, modifiers=["Shift"])

    assert tools.layer.selected_data == {0, 1}


def test_click_on_empty_space_clears_the_selection(tools):
    tools.toolbar._buttons[LASSO].click()
    _draw_lasso(tools.layer, AROUND_FIRST)
    _draw_lasso(tools.layer, [(50, 50)])

    assert len(tools.lassos) == 1  # the click is not hit-tested
    assert tools.layer.selected_data == set()
    assert tools.layer.mode == "select"


def test_escape_cancels_the_lasso_being_drawn(tools):
    tools.toolbar._buttons[LASSO].click()
    drag, event = _press(tools.layer, (-5, -5))
    _move(drag, event, (-5, 15))

    keymap = {str(key): func for key, func in tools.layer.keymap.items()}
    keymap["Escape"](tools.layer)
    assert not tools.lasso.is_drawing
    _release(drag, event)
    assert tools.lassos == []
    assert tools.layer.mode == "select"

    # Escape is only bound while the lasso is active
    tools.toolbar._buttons["direct"].click()
    assert "Escape" not in {str(key) for key in tools.layer.keymap}


def test_tool_changed_while_drawing(tools):
    tools.toolbar._buttons[LASSO].click()
    drag, event = _press(tools.layer, (-5, -5))
    tools.toolbar._buttons["add_polygon"].click()
    _move(drag, event, (-5, 15))
    _release(drag, event)

    # The new tool keeps its mode, nothing is selected
    assert tools.layer.mode == "add_polygon"
    assert tools.lassos == []


def test_lasso_turned_off_by_a_mode_chosen_elsewhere(tools):
    tools.toolbar._buttons[LASSO].click()
    tools.layer.mode = "direct"

    assert tools.toolbar.checked == "direct"
    assert tools.layer.cursor != "cross"


def test_lasso_turned_off_when_another_layer_gets_active(tools):
    other = tools.viewer.add_points([[5, 5]])
    tools.toolbar._buttons[LASSO].click()
    tools.viewer.layers.selection.active = other
    _settle(tools.qtbot)

    assert tools.toolbar.checked is None

    # Choosing a tool makes the edit layer active again
    tools.toolbar._buttons["direct"].click()
    assert tools.viewer.layers.selection.active is tools.layer
    assert tools.layer.mode == "direct"


def test_outline_follows_napari_highlight_preferences(tools):
    from napari.settings import get_settings

    highlight = get_settings().appearance.highlight
    previous = (list(highlight.highlight_color), highlight.highlight_thickness)
    tools.toolbar._buttons[LASSO].click()
    outline = tools.outline.layer
    tools.lasso._outline.show(np.array(AROUND_FIRST))
    try:
        highlight.highlight_color = [1.0, 0.0, 0.0, 1.0]
        width = outline.edge_width[0]
        highlight.highlight_thickness = highlight.highlight_thickness * 2
        np.testing.assert_allclose(outline.edge_color[0], [1, 0, 0, 1])
        assert outline.edge_width[0] == pytest.approx(width * 2)
    finally:
        highlight.highlight_color, highlight.highlight_thickness = previous


def test_outline_keeps_its_screen_width(tools):
    tools.toolbar._buttons[LASSO].click()
    outline = tools.outline.layer
    tools.lasso._outline.show(np.array(AROUND_FIRST))
    width = outline.edge_width[0]

    tools.viewer.camera.zoom *= 2
    assert outline.edge_width[0] == pytest.approx(width / 2)


def test_line_select_tool_draws_an_open_line(make_napari_viewer):
    from napari_roxas_ai._edition._tools import (
        LINE_SELECT,
        LineSelectTool,
        StrokeSelectTool,
    )

    viewer = make_napari_viewer()
    layer = viewer.add_shapes([SQUARE], shape_type="polygon")
    outline = SelectionOutline.add(viewer, layer).layer
    line = LineSelectTool(viewer)
    assert isinstance(line, StrokeSelectTool)
    toolbar = ToolBar(viewer, shapes_rows([line]))
    tools = LayerTools(viewer, toolbar, custom_tools=[line])
    tools.attach(layer)
    toolbar._buttons[LINE_SELECT].click()

    drag, event = _press(layer, (5, -5))
    _move(drag, event, (5, 15))
    # The outline is an open line, not closed back
    assert outline.shape_type == ["path"]
    _release(drag, event)
    # 2 points are a line: it crosses the square, which gets selected
    assert layer.selected_data == {0}


# -- Hit tests --


def test_lasso_vertex_criteria():
    """
    1. Cell completely inside lasso -> in
    2. Cell completely outside lasso -> out
    3. One cell vertex inside lasso -> in
    4. Lasso crosses cell edges but no cell vertex inside -> out
    5. Cell vertex on lasso boundary -> in
    """
    cell_inside = np.array(
        [[25, 25], [25, 35], [35, 35], [35, 25]], dtype=np.float32
    )
    cell_outside = np.array(
        [[70, 70], [70, 80], [80, 80], [80, 70]], dtype=np.float32
    )
    cell_one_vertex_inside = np.array(
        [[38, 38], [50, 60], [60, 60], [60, 50]], dtype=np.float32
    )
    cell_crossing_no_vertex = np.array(
        [[10, 28], [10, 32], [50, 32], [50, 28]], dtype=np.float32
    )
    cell_on_boundary = np.array(
        [[20, 30], [15, 25], [15, 35]], dtype=np.float32
    )
    cells = [
        cell_inside,
        cell_outside,
        cell_one_vertex_inside,
        cell_crossing_no_vertex,
        cell_on_boundary,
    ]
    lasso = np.array(
        [[20, 20], [20, 40], [40, 40], [40, 20]], dtype=np.float32
    )

    assert LassoSelectTool.hits(cells, lasso) == {0, 2, 4}


def test_lasso_near_boundary():
    lasso = np.array([[0, 0], [0, 10], [10, 10], [10, 0]], dtype=np.float32)
    cell_near_0 = np.array([[0, 0], [0, 5], [5, 5], [5, 0]], dtype=np.float32)
    cell_away = np.array(
        [[50, 50], [50, 60], [60, 60], [60, 50]], dtype=np.float32
    )

    assert LassoSelectTool.hits([cell_near_0, cell_away], lasso) == {0}


def test_line_hit_criteria():
    cell_crossed = np.array([[10, 10], [10, 20], [20, 20], [20, 10]], float)
    cell_corner = np.array([[0, 30], [0, 40], [5, 40], [5, 30]], float)
    cell_missed = np.array([[30, 0], [30, 10], [40, 10], [40, 0]], float)
    cell_around_line = np.array(
        [[50, 50], [50, 90], [90, 90], [90, 50]], float
    )
    cells = [cell_crossed, cell_corner, cell_missed, cell_around_line]

    # Crosses the first cell, touches the corner (5, 30) of the second
    line = np.array([[15, 0], [15, 25], [5, 30]], float)
    assert LineSelectTool.hits(cells, line) == {0, 1}
    # Entirely inside a cell
    assert LineSelectTool.hits(
        cells, np.array([[60, 60], [70, 70]], float)
    ) == {3}
    # Between cells, and a click (fewer than 2 points)
    assert (
        LineSelectTool.hits(cells, np.array([[25, 0], [25, 5]], float))
        == set()
    )
    assert LineSelectTool.hits(cells, np.array([[15, 15]], float)) == set()
