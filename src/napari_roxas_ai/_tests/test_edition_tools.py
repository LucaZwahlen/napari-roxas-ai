import numpy as np
import pytest

from napari_roxas_ai._edition._tools import PIXEL, UNDO, VECTOR, EditToolsPanel

SQUARE = np.array([[0, 0], [0, 10], [10, 10], [10, 0]], dtype=float)


@pytest.fixture
def session(make_napari_viewer):
    """A panel with a raster (Labels) edit session."""
    viewer = make_napari_viewer()
    panel = EditToolsPanel(viewer)
    labels = viewer.add_labels(np.zeros((10, 10), dtype=int))
    panel.edit_pixels(labels)
    return panel, labels


def _button(panel, kind, name):
    return panel._tools[kind].toolbar._buttons[name]


def _shown_options(panel, kind):
    box = panel._options[kind]
    return [n for n, w in box._widgets.items() if not w.native.isHidden()]


def test_tool_buttons_set_the_napari_mode(session):
    panel, labels = session
    _button(panel, PIXEL, "paint").click()
    assert labels.mode == "paint"

    shapes = panel._viewer.add_shapes([SQUARE], shape_type="polygon")
    panel.edit_vectors(shapes)
    _button(panel, VECTOR, "add_polygon").click()
    assert shapes.mode == "add_polygon"


def test_mode_chosen_elsewhere_checks_its_button(session):
    panel, labels = session
    labels.mode = "fill"  # e.g. napari's layer controls or a shortcut
    assert _button(panel, PIXEL, "fill").isChecked()
    assert not _button(panel, PIXEL, "paint").isChecked()


def test_options_sync_both_ways(session):
    panel, labels = session
    widgets = panel._options[PIXEL]._widgets

    widgets["brush_size"].value = 23
    assert labels.brush_size == 23
    labels.brush_size = 7
    assert widgets["brush_size"].value == 7

    labels.opacity = 0.4
    assert widgets["opacity"].value == pytest.approx(0.4)
    widgets["opacity"].value = 0.8
    assert labels.opacity == pytest.approx(0.8)


def test_options_follow_the_checked_tool(session):
    panel, labels = session
    titles = panel._options[PIXEL]._titles

    _button(panel, PIXEL, "paint").click()
    assert _shown_options(panel, PIXEL) == ["brush_size", "opacity"]
    labels.mode = "fill"
    assert _shown_options(panel, PIXEL) == ["contiguous", "opacity"]
    _button(panel, PIXEL, "pan_zoom").click()
    assert _shown_options(panel, PIXEL) == ["opacity"]
    # No tool option: only the "Layer options" title
    assert titles["tool"].native.isHidden()
    assert not titles["layer"].native.isHidden()


def test_undo_button_runs_the_editor_undo(session):
    panel, _labels = session
    undone = []
    panel.set_undo(lambda: undone.append(True))
    undo = _button(panel, PIXEL, UNDO)

    assert not undo.isEnabled()  # nothing to undo
    panel.set_undo_enabled(True)
    assert undo.isEnabled()
    undo.click()
    assert undone == [True]
