try:
    import bpy
except ImportError:
    pass

bl_info = {
    "name": "BlendAgent",
    "blender": (4, 0, 0),
    "category": "Object",
}

import bpy
import requests

API_URL = "http://127.0.0.1:8000/plan"


# ------------------------
# SERVER CALL
# ------------------------

def get_node_plan(prompt):
    try:
        response = requests.post(
            API_URL,
            json={"prompt": prompt},
            timeout=10
        )
        response.raise_for_status()
        plan = response.json()
        print("Agent plan:", plan)
        return plan

    except Exception as e:
        print("Server error:", e)
        return {"operation": "unknown", "source": "error"}


# ------------------------
# HELPERS
# ------------------------

def get_active_object():
    return bpy.context.active_object


def get_active_mesh():
    obj = get_active_object()
    if obj is None:
        return None
    if obj.type != 'MESH':
        return None
    return obj


def clear_blendagent_modifiers(obj):
    for mod in list(obj.modifiers):
        if mod.type == 'NODES' and mod.name.startswith("BlendAgent_"):
            obj.modifiers.remove(mod)


def create_geo_node_group(name):
    node_group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    nodes = node_group.nodes
    links = node_group.links

    nodes.clear()

    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")

    input_node.location = (-700, 0)
    output_node.location = (500, 0)

    try:
        node_group.interface.new_socket(
            name="Geometry",
            in_out='INPUT',
            socket_type='NodeSocketGeometry'
        )
        node_group.interface.new_socket(
            name="Geometry",
            in_out='OUTPUT',
            socket_type='NodeSocketGeometry'
        )
    except Exception:
        pass

    return node_group, nodes, links, input_node, output_node


def get_unique_material_for_object(obj, base_name):
    safe_obj_name = obj.name.replace(" ", "_")
    mat_name = f"{base_name}_{safe_obj_name}"

    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)

    mat.use_nodes = True
    return mat


def assign_material_to_object(obj, mat):
    if obj is None:
        return False

    if not hasattr(obj.data, "materials"):
        return False

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return True


def set_material_display_color(mat, rgba):
    try:
        mat.diffuse_color = rgba
    except Exception as e:
        print("Diffuse color set error:", e)


# ------------------------
# GEOMETRY NODE BUILDERS
# ------------------------

def create_subdivide_nodes():
    obj = get_active_mesh()
    if not obj:
        return False

    clear_blendagent_modifiers(obj)

    modifier = obj.modifiers.new(name="BlendAgent_Subdivide", type='NODES')
    node_group, nodes, links, input_node, output_node = create_geo_node_group("BlendAgent_SubdivideNodes")
    modifier.node_group = node_group

    subdivide = nodes.new("GeometryNodeSubdivideMesh")
    subdivide.location = (0, 0)

    if "Level" in subdivide.inputs:
        subdivide.inputs["Level"].default_value = 2

    try:
        links.new(input_node.outputs[0], subdivide.inputs[0])
        links.new(subdivide.outputs[0], output_node.inputs[0])
    except Exception as e:
        print("Subdivide link error:", e)
        return False

    return True


def create_noise_terrain_nodes():
    obj = get_active_mesh()
    if not obj:
        return False

    clear_blendagent_modifiers(obj)

    modifier = obj.modifiers.new(name="BlendAgent_NoiseTerrain", type='NODES')
    node_group, nodes, links, input_node, output_node = create_geo_node_group("BlendAgent_NoiseTerrainNodes")
    modifier.node_group = node_group

    set_position = nodes.new("GeometryNodeSetPosition")
    position = nodes.new("GeometryNodeInputPosition")
    noise = nodes.new("ShaderNodeTexNoise")
    multiply = nodes.new("ShaderNodeMath")
    combine_xyz = nodes.new("ShaderNodeCombineXYZ")

    set_position.location = (160, 0)
    position.location = (-520, -160)
    noise.location = (-320, -160)
    multiply.location = (-120, -160)
    combine_xyz.location = (40, -160)
    output_node.location = (380, 0)

    multiply.operation = 'MULTIPLY'

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 2.5
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 8.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.55

    if len(multiply.inputs) > 1:
        multiply.inputs[1].default_value = 0.8

    try:
        links.new(input_node.outputs[0], set_position.inputs[0])
        links.new(position.outputs[0], noise.inputs[0])
        links.new(noise.outputs[0], multiply.inputs[0])
        links.new(multiply.outputs[0], combine_xyz.inputs[2])
        links.new(combine_xyz.outputs[0], set_position.inputs[3])
        links.new(set_position.outputs[0], output_node.inputs[0])
    except Exception as e:
        print("Noise terrain link error:", e)
        return False

    return True


# ------------------------
# MATERIAL BUILDERS
# ------------------------

def create_glossy_material():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Glossy")
    set_material_display_color(mat, (0.72, 0.84, 1.0, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    bump = nodes.new(type="ShaderNodeBump")
    noise = nodes.new(type="ShaderNodeTexNoise")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")

    texcoord.location = (-800, -120)
    mapping.location = (-600, -120)
    noise.location = (-380, -120)
    bump.location = (-120, -140)
    principled.location = (80, 0)
    output.location = (340, 0)

    if "Base Color" in principled.inputs:
        principled.inputs["Base Color"].default_value = (0.72, 0.84, 1.0, 1.0)
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.03
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 1.0
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.9

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 18.0
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 8.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.45

    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = 0.08
    if "Distance" in bump.inputs:
        bump.inputs["Distance"].default_value = 0.03

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        if "Normal" in principled.inputs:
            links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Glossy material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_toon_material():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Toon")
    set_material_display_color(mat, (1.0, 0.25, 0.95, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
    shader_to_rgb = nodes.new(type="ShaderNodeShaderToRGB")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    emission = nodes.new(type="ShaderNodeEmission")

    diffuse.location = (-500, 0)
    shader_to_rgb.location = (-280, 0)
    ramp.location = (-60, 0)
    emission.location = (180, 0)
    output.location = (420, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.06, 0.06, 0.08, 1.0)
        ramp.color_ramp.elements[1].position = 0.62
        ramp.color_ramp.elements[1].color = (1.0, 0.25, 0.95, 1.0)
    except Exception:
        pass

    if "Strength" in emission.inputs:
        emission.inputs["Strength"].default_value = 1.2
    if "Color" in emission.inputs:
        emission.inputs["Color"].default_value = (1.0, 0.25, 0.95, 1.0)

    try:
        links.new(diffuse.outputs["BSDF"], shader_to_rgb.inputs["Shader"])
        links.new(shader_to_rgb.outputs["Color"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], emission.inputs["Color"])
        links.new(emission.outputs["Emission"], output.inputs["Surface"])
    except Exception as e:
        print("Toon material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_hair_material_basic():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Hair")
    set_material_display_color(mat, (0.30, 0.12, 0.04, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    layer_weight = nodes.new(type="ShaderNodeLayerWeight")
    wave = nodes.new(type="ShaderNodeTexWave")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")
    mixrgb = nodes.new(type="ShaderNodeMixRGB")

    texcoord.location = (-980, -120)
    mapping.location = (-780, -120)
    wave.location = (-560, -120)
    layer_weight.location = (-560, 140)
    ramp.location = (-320, 140)
    mixrgb.location = (-100, 20)
    principled.location = (140, 0)
    output.location = (400, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.10
        ramp.color_ramp.elements[0].color = (0.02, 0.01, 0.005, 1.0)
        ramp.color_ramp.elements[1].position = 0.92
        ramp.color_ramp.elements[1].color = (0.52, 0.22, 0.06, 1.0)
    except Exception:
        pass

    if "Scale" in wave.inputs:
        wave.inputs["Scale"].default_value = 35.0
    if "Distortion" in wave.inputs:
        wave.inputs["Distortion"].default_value = 3.0
    if "Detail" in wave.inputs:
        wave.inputs["Detail"].default_value = 4.0
    if "Detail Scale" in wave.inputs:
        wave.inputs["Detail Scale"].default_value = 1.5

    if "Blend" in layer_weight.inputs:
        layer_weight.inputs["Blend"].default_value = 0.18

    if "Fac" in mixrgb.inputs:
        mixrgb.inputs["Fac"].default_value = 0.45

    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.12
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 1.0
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.95

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
        links.new(layer_weight.outputs["Facing"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], mixrgb.inputs[1])
        links.new(wave.outputs["Color"], mixrgb.inputs[2])
        links.new(mixrgb.outputs["Color"], principled.inputs["Base Color"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Hair material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


def create_eye_material_basic():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_unique_material_for_object(obj, "BlendAgent_Eye")
    set_material_display_color(mat, (0.0, 0.65, 1.0, 1.0))

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    gradient = nodes.new(type="ShaderNodeTexGradient")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")
    ramp = nodes.new(type="ShaderNodeValToRGB")

    texcoord.location = (-980, -120)
    mapping.location = (-760, -120)
    gradient.location = (-540, -120)
    ramp.location = (-300, -120)
    principled.location = (20, 0)
    output.location = (280, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.05
        ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1.0)
        ramp.color_ramp.elements[1].position = 0.80
        ramp.color_ramp.elements[1].color = (0.0, 0.65, 1.0, 1.0)
    except Exception:
        pass

    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.02
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 1.0
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 1.0

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], gradient.inputs["Vector"])
        links.new(gradient.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Eye material link error:", e)
        return False

    return assign_material_to_object(obj, mat)


# ------------------------
# OPERATOR
# ------------------------

class BLENDAGENT_OT_generate(bpy.types.Operator):
    bl_idname = "blendagent.generate"
    bl_label = "Generate"

    def execute(self, context):
        prompt = context.scene.blendagent_prompt.lower().strip()
        plan = get_node_plan(prompt)
        op = str(plan.get("operation", "")).lower()

        print("Prompt:", prompt)
        print("Operation from agent:", op)

        executed = False

        if "eye" in op:
            executed = create_eye_material_basic()

        elif "hair" in op:
            executed = create_hair_material_basic()

        elif "toon" in op:
            executed = create_toon_material()

        elif "glossy" in op:
            executed = create_glossy_material()

        elif "noise" in op or "terrain" in op:
            executed = create_noise_terrain_nodes()

        elif "subdivide" in op:
            executed = create_subdivide_nodes()

        elif "eye" in prompt or "iris" in prompt or "cornea" in prompt:
            print("Fallback eye material triggered")
            executed = create_eye_material_basic()

        elif "hair" in prompt or "bangs" in prompt or "strands" in prompt:
            print("Fallback hair material triggered")
            executed = create_hair_material_basic()

        elif "toon" in prompt or "anime" in prompt or "stylized" in prompt or "cartoon" in prompt:
            print("Fallback toon material triggered")
            executed = create_toon_material()

        elif "glossy" in prompt or "shiny" in prompt or "reflective" in prompt:
            print("Fallback glossy triggered")
            executed = create_glossy_material()

        elif "noise" in prompt or "terrain" in prompt or "hills" in prompt or "rocky" in prompt:
            print("Fallback noise terrain triggered")
            executed = create_noise_terrain_nodes()

        elif "subdivide" in prompt or "smooth" in prompt:
            print("Fallback subdivide triggered")
            executed = create_subdivide_nodes()

        else:
            self.report({'WARNING'}, f"Unknown operation: {op}")
            return {'CANCELLED'}

        if not executed:
            self.report({'WARNING'}, "Operation failed. Check console for node/material errors.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Applied: {op if op else 'fallback'}")
        return {'FINISHED'}


# ------------------------
# UI PANEL
# ------------------------

class BLENDAGENT_PT_panel(bpy.types.Panel):
    bl_label = "BlendAgent"
    bl_idname = "BLENDAGENT_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "BlendAgent"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object

        box = layout.box()
        box.label(text="Context")

        if obj:
            box.label(text=f"Selected: {obj.name}")
            box.label(text=f"Type: {obj.type}")
        else:
            box.label(text="Selected: None")

        layout.prop(scene, "blendagent_prompt")
        layout.operator("blendagent.generate", text="Generate")

        help_box = layout.box()
        help_box.label(text="Examples")
        help_box.label(text="• make this glossy")
        help_box.label(text="• make this toon")
        help_box.label(text="• make this hair shiny")
        help_box.label(text="• make this eye shiny")
        help_box.label(text="• add terrain noise")
        help_box.label(text="• subdivide mesh")


# ------------------------
# PROPERTIES
# ------------------------

def register_properties():
    bpy.types.Scene.blendagent_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Describe what to generate",
        default="make this hair shiny"
    )


def unregister_properties():
    if hasattr(bpy.types.Scene, "blendagent_prompt"):
        del bpy.types.Scene.blendagent_prompt


# ------------------------
# REGISTER
# ------------------------

classes = (
    BLENDAGENT_OT_generate,
    BLENDAGENT_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()


def unregister():
    unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()