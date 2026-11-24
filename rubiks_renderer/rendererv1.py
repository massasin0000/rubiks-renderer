import pygame
import ctypes
import math
from io import StringIO
from pathlib import Path
import numpy as np
import moderngl as mgl # type: ignore
import time


parent_file = Path(__file__).parent
path = parent_file / "rfc.vl"

vertex_list = np.empty((0, 4), dtype=np.float32)
triangle_list = np.empty((0, 7), dtype=np.float32)
material_list = np.empty((0, 4), dtype=np.float32)



try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def load_objekt():
    global vertex_list, triangle_list, material_list

    sections = {"vtr": [], "tri": [], "mtr": []}
    current_section = None

    with path.open("r", encoding="utf-8") as datei:
        for line in datei:
            line = line.strip()
            if line in sections:
                current_section = line
            elif line and current_section is not None:
                sections[current_section].append(line)

    def load_section(name, columns):
        lines = sections[name]
        if not lines:
            return np.empty((0, columns), dtype=np.float32)
        return np.loadtxt(
            StringIO("\n".join(lines)),
            delimiter=",",
            dtype=np.float32,
            ndmin=2,
        )

    vertex_list = load_section("vtr", 4)
    triangle_list = load_section("tri", 7)
    material_list = load_section("mtr", 4)

    print("dreiecke", len(triangle_list), "vertex", len(vertex_list))

def load_vl_file(model_file):
    model_path = Path(model_file)
    if not model_path.is_absolute():
        model_path = parent_file / model_path

    sections = {"vtr": [], "tri": [], "mtr": []}
    current_section = None

    with model_path.open("r", encoding="utf-8") as datei:
        for line in datei:
            line = line.strip()
            if line in sections:
                current_section = line
            elif line and current_section is not None:
                sections[current_section].append(line)

    def load_section(name, columns):
        lines = sections[name]
        if not lines:
            return np.empty((0, columns), dtype=np.float32)
        return np.loadtxt(
            StringIO("\n".join(lines)),
            delimiter=",",
            dtype=np.float32,
            ndmin=2,
        )

    return (
        load_section("vtr", 4),
        load_section("tri", 7),
        load_section("mtr", 4),
    )

def filter_sort_list(list):
    filter = [punkt for punkt in list if punkt[2] > 0]
    return sorted(filter, key=lambda punkt: punkt[2])

def calctanandm():
    global fovvt, fovht, fovv, fovh, roth, rotv,m1,m2,m3,m4,m5,m6,m7,m8
    fovvt = math.tan(math.radians(fovv)/2)*2
    fovht = math.tan(math.radians(fovh)/2)*2
    a=math.radians(-roth)  
    b=math.radians(-rotv)
    m1=math.cos(a)
    m2=math.sin(a)
    m4=math.cos(b)
    m7=math.sin(b)
    m3=m2*m7
    m5=-m1*m7
    m6=-m2*m4
    m8=m1*m4

def clip_polygon_near(polygon, near_plane):
    clipped = []

    for current, following in zip(polygon, polygon[1:] + polygon[:1]):
        current_inside = current[2] >= near_plane
        following_inside = following[2] >= near_plane

        if current_inside != following_inside:
            distance = (near_plane - current[2]) / (following[2] - current[2])
            clipped.append(tuple(
                current[index] + distance * (following[index] - current[index])
                for index in range(3)
            ))

        if current_inside:
            clipped.append(current)

    return clipped

def calc_tri_vectorized(vtr, triangle_list):
    global ttd,m1,m2,m3,m4,m5,m6,m7,m8
    ttd = []
    near_plane = 0.1

    punkte_map = {punkt[6]: punkt for punkt in vtr}
    
    for v1, v2,v3,mtr, nx,ny,nz in triangle_list:
        if v1 in punkte_map and v2 in punkte_map and v3 in punkte_map:
            #nx, ny, nz = rotate_normal(nx, ny, nz)
            old_nx, old_ny, old_nz = nx, ny, nz
            nx = old_nx*m1 + old_nz*m2
            ny = old_nx*m3 + old_ny*m4 + old_nz*m5
            nz = old_nx*m6 + old_ny*m7 + old_nz*m8

            v1x, v1y, v1z, x1, y1, z1, _ = punkte_map[v1]
            #backface_visible = back_face_culling(nx, ny, nz, x1, y1, z1)

            #if backface_visible > 0:
            if (nx * -x1) + (ny * -y1) + (nz * -z1) > 0:
                polygon = clip_polygon_near(
                    [
                        (x1, y1, z1),
                        (punkte_map[v2][3], punkte_map[v2][4], punkte_map[v2][5]),
                        (punkte_map[v3][3], punkte_map[v3][4], punkte_map[v3][5]),
                    ],
                    near_plane,
                )

                if len(polygon) >= 3:
                    projected = [
                        (
                            point[0] * height / (point[2] * fovht),
                            point[1] * height / (point[2] * fovvt),
                            point[2],
                        )
                        for point in polygon
                    ]

                    for index in range(1, len(projected) - 1):
                        point_a, point_b, point_c = projected[0], projected[index], projected[index + 1]
                        average_z = (point_a[2] + point_b[2] + point_c[2]) / 3
                        ttd.append((
                            point_a[0], point_a[1],
                            point_b[0], point_b[1],
                            point_c[0], point_c[1],
                            mtr, average_z,
                        ))

    ttd.sort(key=lambda triangle: triangle[7], reverse=True)

def calc_tri(vtr, triangle_list):
    near_plane = 0.1
    indices = triangle_list[:, :3].astype(np.intp)
    triangles = vtr[indices, 3:6]
    normals = triangle_list[:, 4:7]

    camera_normals = np.empty_like(normals)
    camera_normals[:, 0] = normals[:, 0] * m1 + normals[:, 2] * m2
    camera_normals[:, 1] = (
        normals[:, 0] * m3
        + normals[:, 1] * m4
        + normals[:, 2] * m5
    )
    camera_normals[:, 2] = (
        normals[:, 0] * m6
        + normals[:, 1] * m7
        + normals[:, 2] * m8
    )

    visible = np.sum(camera_normals * -triangles[:, 0, :], axis=1) > 0
    triangles = triangles[visible]
    materials = triangle_list[:, 3]
    materials = materials[visible]
    inside = triangles[:, :, 2] >= near_plane
    inside_count = inside.sum(axis=1)
    result = []

    def project(triangle_batch, material_batch):
        if len(triangle_batch) == 0:
            return np.empty((0, 11), dtype=np.float32)

        projected = np.empty_like(triangle_batch)
        projected[:, :, 0] = triangle_batch[:, :, 0] * height / (
            triangle_batch[:, :, 2] * fovht
        )
        projected[:, :, 1] = triangle_batch[:, :, 1] * height / (
            triangle_batch[:, :, 2] * fovvt
        )
        projected[:, :, 2] = triangle_batch[:, :, 2]

        output = np.empty((len(projected), 11), dtype=np.float32)
        output[:, :9] = projected.reshape(-1, 9)
        output[:, 9] = material_batch
        output[:, 10] = projected[:, :, 2].mean(axis=1)
        return output

    all_inside = inside_count == 3
    result.append(project(
        triangles[all_inside],
        materials[all_inside],
    ))

    one_inside = inside_count == 1
    if np.any(one_inside):
        clipped_triangles = triangles[one_inside]
        clipped_inside = inside[one_inside]
        clipped_materials = materials[one_inside]
        rows = np.arange(len(clipped_triangles))
        inside_index = np.argmax(clipped_inside, axis=1)
        previous_index = (inside_index + 2) % 3
        next_index = (inside_index + 1) % 3

        inside_vertex = clipped_triangles[rows, inside_index]
        next_vertex = clipped_triangles[rows, next_index]
        previous_vertex = clipped_triangles[rows, previous_index]

        def intersect(first, second):
            distance = (near_plane - first[:, 2]) / (second[:, 2] - first[:, 2])
            return first + distance[:, None] * (second - first)

        next_intersection = intersect(inside_vertex, next_vertex)
        previous_intersection = intersect(previous_vertex, inside_vertex)
        result.append(project(
            np.stack((inside_vertex, next_intersection, previous_intersection), axis=1),
            clipped_materials,
        ))

    two_inside = inside_count == 2
    if np.any(two_inside):
        clipped_triangles = triangles[two_inside]
        clipped_inside = inside[two_inside]
        clipped_materials = materials[two_inside]
        rows = np.arange(len(clipped_triangles))
        outside_index = np.argmax(~clipped_inside, axis=1)
        previous_index = (outside_index + 2) % 3
        next_index = (outside_index + 1) % 3

        previous_vertex = clipped_triangles[rows, previous_index]
        outside_vertex = clipped_triangles[rows, outside_index]
        next_vertex = clipped_triangles[rows, next_index]

        def intersect(first, second):
            distance = (near_plane - first[:, 2]) / (second[:, 2] - first[:, 2])
            return first + distance[:, None] * (second - first)

        previous_intersection = intersect(previous_vertex, outside_vertex)
        next_intersection = intersect(outside_vertex, next_vertex)
        result.append(project(
            np.stack((previous_vertex, previous_intersection, next_intersection), axis=1),
            clipped_materials,
        ))
        result.append(project(
            np.stack((previous_vertex, next_intersection, next_vertex), axis=1),
            clipped_materials,
        ))

    if not result:
        return np.empty((0, 11), dtype=np.float32)

    result = np.concatenate(result)
    return result[np.argsort(result[:, 10])[::-1]]

def draw_tri(ttd):
    if len(ttd) == 0:
        return np.empty((0, 6), dtype=np.float32)

    triangles = np.asarray(ttd, dtype=np.float32)
    positions = triangles[:, :9].reshape(-1, 3)
    camera_z = positions[:, 2]
    near_plane = 0.1
    far_plane = 1000.0
    depth = (
        far_plane + near_plane - (2 * far_plane * near_plane / camera_z)
    ) / (far_plane - near_plane)
    screen_positions = np.empty_like(positions)
    screen_positions[:, 0] = positions[:, 0] * 2 / width
    screen_positions[:, 1] = positions[:, 1] * 2 / height
    screen_positions[:, 2] = depth

    material_indices = triangles[:, 9].astype(np.intp)
    colors = material_list[material_indices, 1:4] / 255.0
    colors = np.repeat(colors, 3, axis=0)

    return np.column_stack((screen_positions, colors)).astype(np.float32)

def rotate_normal(nx,ny,nz):
    global m1,m2,m3,m4,m5,m6,m7,m8
    return (
        nx * m1 + nz * m2,
        nx * m3 + ny * m4 + nz * m5,
        nx * m6 + ny * m7 + nz * m8,
    )

def back_face_culling(nx, ny, nz, px,py,pz):
    dot = (nx * -px) + (ny * -py) + (nz * -pz)
    return dot


class Renderer:
    def __init__(self, model_file="modell.vl"):
        pygame.init()

        global path, width, height, camx, camy, camz
        global fovh, fovv, roth, rotv

        self.models = {}
        self.objects = []
        self._next_object_id = 0

        if model_file is not None:
            model_name = self.load_model(model_file)
            self.create_object(model_name)

        pygame.display.gl_set_attribute(pygame.GL_DEPTH_SIZE, 24)
        self.screen = pygame.display.set_mode(
            (1280, 720),
            pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE,
        )
        pygame.display.set_caption("3d Renderer")

        width, height = self.screen.get_size()
        self.width = width
        self.height = height

        self.ctx = mgl.create_context()
        self.prog = self.ctx.program(
            vertex_shader="""
            #version 330
            in vec3 in_pos;
            in vec3 in_color;
            out vec3 v_color;
            void main() {
                gl_Position = vec4(in_pos, 1.0);
                v_color = in_color;
            }
            """,
            fragment_shader="""
            #version 330
            in vec3 v_color;
            out vec4 f_color;
            void main() {
                f_color = vec4(v_color, 1.0);
            }
            """,
        )

        self.vbo = self.ctx.buffer(reserve=1_000_000)
        self.vao = self.ctx.vertex_array(
            self.prog,
            [(self.vbo, "3f 3f", "in_pos", "in_color")],
        )
        self.ctx.enable(mgl.DEPTH_TEST)

        camx = 0.0
        camy = 0.0
        camz = 10.0
        fovh = 90.0
        fovv = 90.0
        roth = 0.0
        rotv = 0.0
        calctanandm()

        self.speed = 12.0
        self.last_time = time.perf_counter()
        self.closed = False

        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        self.mouse_center = (width // 2, height // 2)
        pygame.mouse.set_pos(self.mouse_center)
        pygame.event.clear(pygame.MOUSEMOTION)
        self.ignore_next_mouse_motion = True

        pygame.event.pump()
        self.render()

    def load_model(self, model_file, model_name=None):
        if model_name is None:
            model_name = str(model_file)

        if model_name not in self.models:
            vertices, triangles, materials = load_vl_file(model_file)
            self.models[model_name] = (
                vertices,
                triangles,
                materials,
            )
        return model_name

    def create_object(
        self,
        model_name,
        name=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
    ):
        if model_name not in self.models:
            model_name = self.load_model(model_name)

        if name is None:
            name = f"object_{self._next_object_id}"

        if any(
            isinstance(scene_object, dict)
            and scene_object["name"] == name
            for scene_object in self.objects
        ):
            raise ValueError(f"Object name already exists: {name}")

        object_data = {
            "name": name,
            "model": model_name,
            "position": np.array(position, dtype=np.float32),
            "rotation": np.array(rotation, dtype=np.float32),
            "scale": np.array(scale, dtype=np.float32),
        }
        self.objects.append(object_data)
        self._next_object_id += 1
        return object_data

    def add_object(
        self,
        model_file,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        name=None,
    ):
        model_name = self.load_model(model_file)
        return self.create_object(
            model_name,
            name=name,
            position=position,
            rotation=rotation,
            scale=scale,
        )

    def _get_object(self, object_data):
        if isinstance(object_data, str):
            for scene_object in self.objects:
                if scene_object["name"] == object_data:
                    return scene_object
            raise KeyError(f"Object not found: {object_data}")

        if isinstance(object_data, int):
            if 0 <= object_data < len(self.objects):
                return self.objects[object_data]
            raise IndexError("Object index out of range")

        if isinstance(object_data, dict):
            if any(scene_object is object_data for scene_object in self.objects):
                return object_data
            raise ValueError("Object is not in the scene")

        raise TypeError("Object must be a name, index, or object reference")

    def remove_object(self, object_data):
        scene_object = self._get_object(object_data)
        self.objects.remove(scene_object)
        return scene_object

    def set_position(self, object_data, position):
        scene_object = self._get_object(object_data)
        scene_object["position"] = np.array(position, dtype=np.float32)
        return scene_object

    def move_object(self, object_data, offset):
        scene_object = self._get_object(object_data)
        scene_object["position"] += np.array(offset, dtype=np.float32)
        return scene_object

    def set_rotation(self, object_data, rotation):
        scene_object = self._get_object(object_data)
        scene_object["rotation"] = np.array(rotation, dtype=np.float32)
        return scene_object

    def rotate_object(self, object_data, offset):
        scene_object = self._get_object(object_data)
        scene_object["rotation"] += np.array(offset, dtype=np.float32)
        return scene_object

    def set_scale(self, object_data, scale):
        scene_object = self._get_object(object_data)
        scale_array = np.array(scale, dtype=np.float32)
        if np.any(scale_array <= 0):
            raise ValueError("Scale values must be greater than zero")
        scene_object["scale"] = scale_array
        return scene_object

    def scale_object(self, object_data, factor):
        scene_object = self._get_object(object_data)

        factor_array = np.array(factor, dtype=np.float32)
        if np.any(factor_array <= 0):
            raise ValueError("Scale factor values must be greater than zero")
        scene_object["scale"] *= factor_array
        return scene_object

    def set_triangle_color(self, object_data, triangle_indices, color):
        scene_object = self._get_object(object_data)
        vertices, triangles, materials = self.models[scene_object["model"]]

        if isinstance(triangle_indices, int):
            triangle_indices = [triangle_indices]
        else:
            triangle_indices = list(triangle_indices)

        if len(color) != 3:
            raise ValueError("Color must contain RGB values")

        rgb = np.array(color, dtype=np.float32)
        if np.any(rgb < 0) or np.any(rgb > 255):
            raise ValueError("RGB values must be between 0 and 255")

        if "triangle_color_overrides" not in scene_object:
            scene_object["triangle_color_overrides"] = {}

        overrides = scene_object["triangle_color_overrides"]
        for triangle_index in triangle_indices:
            if not isinstance(triangle_index, int):
                raise TypeError("Triangle indices must be integers")
            if not 0 <= triangle_index < len(triangles):
                raise IndexError("Triangle index out of range")
            overrides[triangle_index] = tuple(rgb)

        return scene_object

    def reset_triangle_colors(self, object_data):
        scene_object = self._get_object(object_data)
        scene_object.pop("triangle_color_overrides", None)
        return scene_object

    def begin_frame(self):
        now = time.perf_counter()
        dt = now - self.last_time
        self.last_time = now
        return dt

    def handle_event(self, event):
        global roth, rotv

        if event.type == pygame.MOUSEMOTION:
            if self.ignore_next_mouse_motion:
                self.ignore_next_mouse_motion = False
                pygame.mouse.set_pos(self.mouse_center)
                return

            if event.pos != self.mouse_center:
                roth += event.rel[0] * 0.1
                rotv += event.rel[1] * 0.1
                rotv = max(-89.0, min(89.0, rotv))
                pygame.mouse.set_pos(self.mouse_center)

        elif event.type == pygame.VIDEORESIZE:
            pygame.display.set_mode(
                event.size,
                pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE,
            )
            global width, height
            width, height = event.size
            self.width = width
            self.height = height
            self.mouse_center = (width // 2, height // 2)
            pygame.mouse.set_pos(self.mouse_center)

    def update_camera(self, keys, dt):
        global camx, camy, camz

        winkel = math.radians(roth)
        forward_x = math.sin(winkel)
        forward_z = math.cos(winkel)
        right_z = -math.sin(winkel)
        right_x = math.cos(winkel)

        movement = self.speed * dt

        if keys[pygame.K_w]:
            camx -= movement * forward_x
            camz -= movement * forward_z
        if keys[pygame.K_s]:
            camx += movement * forward_x
            camz += movement * forward_z
        if keys[pygame.K_a]:
            camz += movement * right_z
            camx += movement * right_x
        if keys[pygame.K_d]:
            camz -= movement * right_z
            camx -= movement * right_x
        if keys[pygame.K_SPACE]:
            camy -= movement
        if keys[pygame.K_LSHIFT]:
            camy += movement

    def render(self):
        global vertex_list, triangle_list, material_list

        self.ctx.viewport = (0, 0, self.width, self.height)

        vertex_parts = []
        triangle_parts = []
        material_parts = []
        vertex_offset = 0
        material_offset = 0

        for scene_object in self.objects:
            vertices, triangles, materials = self.models[scene_object["model"]]
            transformed_vertices = vertices[:, :3].copy()
            transformed_vertices *= scene_object["scale"]

            rotation_x, rotation_y, rotation_z = np.radians(
                scene_object["rotation"]
            )

            if rotation_x:
                cosine, sine = np.cos(rotation_x), np.sin(rotation_x)
                y = transformed_vertices[:, 1].copy()
                z = transformed_vertices[:, 2].copy()
                transformed_vertices[:, 1] = y * cosine - z * sine
                transformed_vertices[:, 2] = y * sine + z * cosine

            if rotation_y:
                cosine, sine = np.cos(rotation_y), np.sin(rotation_y)
                x = transformed_vertices[:, 0].copy()
                z = transformed_vertices[:, 2].copy()
                transformed_vertices[:, 0] = x * cosine + z * sine
                transformed_vertices[:, 2] = -x * sine + z * cosine

            if rotation_z:
                cosine, sine = np.cos(rotation_z), np.sin(rotation_z)
                x = transformed_vertices[:, 0].copy()
                y = transformed_vertices[:, 1].copy()
                transformed_vertices[:, 0] = x * cosine - y * sine
                transformed_vertices[:, 1] = x * sine + y * cosine

            transformed_vertices += scene_object["position"]

            vertices_with_ids = np.empty((len(transformed_vertices), 4), dtype=np.float32)
            vertices_with_ids[:, :3] = transformed_vertices
            vertices_with_ids[:, 3] = np.arange(
                vertex_offset,
                vertex_offset + len(transformed_vertices),
            )
            vertex_parts.append(vertices_with_ids)

            world_triangles = triangles.copy()
            world_triangles[:, :3] += vertex_offset
            world_triangles[:, 3] += material_offset

            normals = world_triangles[:, 4:7].copy()

            if rotation_x:
                cosine, sine = np.cos(rotation_x), np.sin(rotation_x)
                y = normals[:, 1].copy()
                z = normals[:, 2].copy()
                normals[:, 1] = y * cosine - z * sine
                normals[:, 2] = y * sine + z * cosine

            if rotation_y:
                cosine, sine = np.cos(rotation_y), np.sin(rotation_y)
                x = normals[:, 0].copy()
                z = normals[:, 2].copy()
                normals[:, 0] = x * cosine + z * sine
                normals[:, 2] = -x * sine + z * cosine

            if rotation_z:
                cosine, sine = np.cos(rotation_z), np.sin(rotation_z)
                x = normals[:, 0].copy()
                y = normals[:, 1].copy()
                normals[:, 0] = x * cosine - y * sine
                normals[:, 1] = x * sine + y * cosine

            world_triangles[:, 4:7] = normals
            triangle_parts.append(world_triangles)

            world_materials = materials.copy()
            world_materials[:, 0] += material_offset

            overrides = scene_object.get("triangle_color_overrides", {})
            for triangle_index, rgb in overrides.items():
                override_material_index = material_offset + len(world_materials)
                world_triangles[triangle_index, 3] = override_material_index
                world_materials = np.vstack((
                    world_materials,
                    np.array(
                        [[override_material_index, *rgb]],
                        dtype=np.float32,
                    ),
                ))

            material_parts.append(world_materials)

            vertex_offset += len(transformed_vertices)
            material_offset += len(world_materials)

        if not vertex_parts:
            vertex_list = np.empty((0, 4), dtype=np.float32)
            triangle_list = np.empty((0, 7), dtype=np.float32)
            material_list = np.empty((0, 4), dtype=np.float32)
        else:
            vertex_list = np.concatenate(vertex_parts)
            triangle_list = np.concatenate(triangle_parts)
            material_list = np.concatenate(material_parts)

        calctanandm()

        x = vertex_list[:, 0] + camx
        y = vertex_list[:, 1] + camy
        z = vertex_list[:, 2] + camz

        camera_x = x * m1 + z * m2
        camera_y = x * m3 + y * m4 + z * m5
        camera_z = x * m6 + y * m7 + z * m8

        safe_z = np.where(
            np.abs(camera_z) < 1e-6,
            np.where(camera_z < 0, -1e-6, 1e-6),
            camera_z,
        )

        vtr = np.empty((len(vertex_list), 7), dtype=np.float32)
        vtr[:, 0] = camera_x * height / (safe_z * fovht)
        vtr[:, 1] = camera_y * height / (safe_z * fovvt)
        vtr[:, 2] = camera_z
        vtr[:, 3] = camera_x
        vtr[:, 4] = camera_y
        vtr[:, 5] = camera_z
        vtr[:, 6] = vertex_list[:, 3]

        ttd = calc_tri(vtr, triangle_list)
        verts = draw_tri(ttd)

        data = verts.tobytes()
        if len(data) > self.vbo.size:
            self.vbo.orphan(len(data) * 2)
        self.vbo.write(data)
        self.ctx.clear(0, 0, 0, depth=1.0)
        self.vao.render(mgl.TRIANGLES, vertices=len(verts))
        pygame.display.flip()

    def close(self):
        if self.closed:
            return

        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)
        pygame.quit()
        self.closed = True


if __name__ == "__main__":
    renderer = Renderer()
    running = True

    while running:
        dt = renderer.begin_frame()

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

    renderer.close()



