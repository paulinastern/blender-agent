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


def get_or_create_material(name="BlendAgentMaterial"):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    return mat


def assign_material_to_active_object(mat):
    obj = get_active_object()
    if obj is None:
        return False

    if not hasattr(obj.data, "materials"):
        return False

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    return True


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

    mat = get_or_create_material("BlendAgent_Glossy")

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
        principled.inputs["Base Color"].default_value = (0.78, 0.80, 0.86, 1.0)
    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.04
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

    return assign_material_to_active_object(mat)


def create_toon_material():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_or_create_material("BlendAgent_Toon")

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
    shader_to_rgb = nodes.new(type="ShaderNodeShaderToRGB")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    emission = nodes.new(type="ShaderNodeEmission")
    mix = nodes.new(type="ShaderNodeMixShader")

    diffuse.location = (-500, 0)
    shader_to_rgb.location = (-280, 0)
    ramp.location = (-60, 0)
    emission.location = (180, 120)
    mix.location = (380, 0)
    output.location = (620, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.08, 0.08, 0.10, 1.0)
        ramp.color_ramp.elements[1].position = 0.65
        ramp.color_ramp.elements[1].color = (0.85, 0.55, 0.95, 1.0)
    except Exception:
        pass

    if "Color" in emission.inputs:
        emission.inputs["Color"].default_value = (0.85, 0.55, 0.95, 1.0)
    if "Strength" in emission.inputs:
        emission.inputs["Strength"].default_value = 1.0

    try:
        links.new(diffuse.outputs["BSDF"], shader_to_rgb.inputs["Shader"])
        links.new(shader_to_rgb.outputs["Color"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], emission.inputs["Color"])
        links.new(ramp.outputs["Alpha"], mix.inputs[0])
        links.new(diffuse.outputs["BSDF"], mix.inputs[1])
        links.new(emission.outputs["Emission"], mix.inputs[2])
        links.new(mix.outputs["Shader"], output.inputs["Surface"])
    except Exception as e:
        print("Toon material link error:", e)
        return False

    return assign_material_to_active_object(mat)


def create_hair_material_basic():
    obj = get_active_object()
    if obj is None:
        return False

    mat = get_or_create_material("BlendAgent_Hair")

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    layer_weight = nodes.new(type="ShaderNodeLayerWeight")
    noise = nodes.new(type="ShaderNodeTexNoise")
    mapping = nodes.new(type="ShaderNodeMapping")
    texcoord = nodes.new(type="ShaderNodeTexCoord")
    mixrgb = nodes.new(type="ShaderNodeMixRGB")

    texcoord.location = (-950, -120)
    mapping.location = (-760, -120)
    noise.location = (-560, -120)
    layer_weight.location = (-560, 120)
    ramp.location = (-320, 120)
    mixrgb.location = (-120, 0)
    principled.location = (120, 0)
    output.location = (380, 0)

    try:
        ramp.color_ramp.elements[0].position = 0.15
        ramp.color_ramp.elements[0].color = (0.05, 0.03, 0.02, 1.0)
        ramp.color_ramp.elements[1].position = 0.85
        ramp.color_ramp.elements[1].color = (0.45, 0.22, 0.08, 1.0)
    except Exception:
        pass

    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 35.0
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 3.0
    if "Roughness" in noise.inputs:
        noise.inputs["Roughness"].default_value = 0.25

    if "Blend" in layer_weight.inputs:
        layer_weight.inputs["Blend"].default_value = 0.25

    if "Fac" in mixrgb.inputs:
        mixrgb.inputs["Fac"].default_value = 0.35

    if "Roughness" in principled.inputs:
        principled.inputs["Roughness"].default_value = 0.18
    if "Metallic" in principled.inputs:
        principled.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in principled.inputs:
        principled.inputs["Specular IOR Level"].default_value = 0.85
    elif "Specular" in principled.inputs:
        principled.inputs["Specular"].default_value = 0.75

    try:
        links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        links.new(layer_weight.outputs["Facing"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], mixrgb.inputs[1])
        links.new(noise.outputs["Color"], mixrgb.inputs[2])
        links.new(mixrgb.outputs["Color"], principled.inputs["Base Color"])
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    except Exception as e:
        print("Hair material link error:", e)
        return False

    return assign_material_to_active_object(mat)


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

        if "subdivide" in op:
            executed = create_subdivide_nodes()

        elif "noise" in op or "terrain" in op:
            executed = create_noise_terrain_nodes()

        elif "toon" in op:
            executed = create_toon_material()

        elif "hair" in op:
            executed = create_hair_material_basic()

        elif "glossy" in op or "material" in op:
            executed = create_glossy_material()

        elif "hair" in prompt:
            print("Fallback hair material triggered")
            executed = create_hair_material_basic()

        elif "toon" in prompt or "anime" in prompt or "stylized" in prompt:
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
        help_box.label(text="• add terrain noise")
        help_box.label(text="• make this glossy")
        help_box.label(text="• make this toon")
        help_box.label(text="• make this hair shiny")
        help_box.label(text="• subdivide mesh")


# ------------------------
# PROPERTIES
# ------------------------

def register_properties():
    bpy.types.Scene.blendagent_prompt = bpy.props.StringProperty(
        name="Prompt",
        description="Describe what to generate",
        default="make this toon"
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