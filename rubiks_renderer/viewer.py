"""Render a Rubik's cube whose face colors can be edited at runtime.

Change the entries in ``top``, ``front``, ``back``, ``bottom``, ``right`` or
``left`` to one of ``"y"``, ``"g"``, ``"b"``, ``"w"``, ``"r"`` or ``"o"``.
While the viewer is running, the displayed colors update automatically.
"""

top = ["w", "b", "y", "g", "y", "y", "o", "y", "y"]
front = ["w", "g", "b", "w", "g", "g", "g", "g", "y"]
back = ["w", "b", "g", "y", "b", "b", "w", "b", "b"]
bottom = ["w", "b", "y", "g", "w", "w", "w", "w", "w"]
right = ["y", "r", "r", "b", "r", "r", "r", "r", "r"]
left = ["y", "o", "o", "b", "o", "o", "o", "o", "o"]

_FACE_NAMES = ("top", "bottom", "front", "back", "left", "right")

def set_cube_state(
    new_top,
    new_front,
    new_back,
    new_bottom,
    new_left,
    new_right,
):
    """Replace all cube faces with new color arrays."""

    global top, front, back, bottom, left, right

    faces = (
        ("top", new_top),
        ("front", new_front),
        ("back", new_back),
        ("bottom", new_bottom),
        ("left", new_left),
        ("right", new_right),
    )

    valid_colors = {"y", "g", "b", "w", "r", "o"}

    for name, face in faces:
        if len(face) != 9:
            raise ValueError(f"{name} must contain exactly 9 entries")

        for color in face:
            if color not in valid_colors:
                raise ValueError(
                    f"Invalid color '{color}' in {name}. "
                    f"Use y, g, b, w, r or o."
                )

    top = list(new_top)
    front = list(new_front)
    back = list(new_back)
    bottom = list(new_bottom)
    left = list(new_left)
    right = list(new_right)


def getcolor(color):
    """Translate a cube color code into an RGB tuple."""
    colors = {
        "y": (255, 213, 0),
        "g": (0, 155, 72),
        "b": (0, 70, 173),
        "w": (242, 242, 242),
        "r": (183, 18, 52),
        "o": (255, 88, 0),
    }
    return colors.get(color, (128, 128, 128))


def _color_state():
    return tuple(tuple(globals()[face]) for face in _FACE_NAMES)


def create_renderer():
    from pathlib import Path

    from .rendererv1 import Renderer

    model_file = Path(__file__).with_name("rcf.vl")
    renderer = Renderer(model_file=str(model_file))

    face_layouts = (
        (
            (lambda i: (-2.0 + (i % 3) * 2.0, 3.0, -1.0 + (i // 3) * 2.0)),
            (90.0, 0.0, 0.0),
        ),
        (
            (lambda i: (-2.0 + (i % 3) * 2.0, -3.0, -1.0 + (i // 3) * 2.0)),
            (-90.0, 0.0, 0.0),
        ),
        (
            (lambda i: (-2.0 + (i % 3) * 2.0, -2.0 + (i // 3) * 2.0, -2.0)),
            (0.0, 0.0, 0.0),
        ),
        (
            (lambda i: (-2.0 + (i % 3) * 2.0, -2.0 + (i // 3) * 2.0, 4.0)),
            (0.0, 180.0, 0.0),
        ),
        (
            (lambda i: (-3.0, -2.0 + (i // 3) * 2.0, -1.0 + (i % 3) * 2.0)),
            (0.0, 90.0, 0.0),
        ),
        (
            (lambda i: (3.0, -2.0 + (i // 3) * 2.0, -1.0 + (i % 3) * 2.0)),
            (0.0, -90.0, 0.0),
        ),
    )

    for position_for, rotation in face_layouts:
        for i in range(9):
            cube_tile = renderer.add_object(
                str(model_file),
                position=position_for(i),
                scale=(1.0, 1.0, 1.0),
            )
            renderer.rotate_object(cube_tile, rotation)

    return renderer


def update_colors(renderer):
    """Apply the current face arrays to an existing renderer."""
    faces = tuple(globals()[face] for face in _FACE_NAMES)
    for face_name, colors in zip(_FACE_NAMES, faces):
        if len(colors) != 9:
            raise ValueError(f"{face_name} must contain exactly 9 colors")

    for face_index, colors in enumerate(faces):
        first_object = face_index * 9 + 1
        for tile_index, color in enumerate(colors):
            rgb = getcolor(color)
            object_index = first_object + tile_index
            renderer.set_triangle_color(object_index, 0, rgb)
            renderer.set_triangle_color(object_index, 1, rgb)


def main():
    """Run the interactive cube viewer."""
    import pygame

    renderer = create_renderer()
    try:
        previous_colors = None
        running = True

        while running:
            dt = renderer.begin_frame()
            current_colors = _color_state()
            if current_colors != previous_colors:
                update_colors(renderer)
                previous_colors = current_colors

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                else:
                    renderer.handle_event(event)

            keys = pygame.key.get_pressed()
            renderer.update_camera(keys, dt)
            renderer.render()
    finally:
        renderer.close()


if __name__ == "__main__":
    main()
