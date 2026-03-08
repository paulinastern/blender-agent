try:
    import bpy
except ImportError:
    pass

bl_info = {
    "name": "BlendAgent",
    "blender": (3, 0, 0),
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

        plan = response.json()

        print("Agent plan:", plan)

        return plan

    except Exception as e:

        print("Server error:", e)

        return {"operation": "unknown"}


# ------------------------
# NODE BUILDERS
# ------------------------

def create_subdivide_nodes():

    obj = bpy.context.active_object

    modifier = obj.modifiers.new(name="GeoNodes", type='NODES')

    node_group = bpy.data.node_groups.new("SubdivideNodes", 'GeometryNodeTree')
    modifier.node_group = node_group

    nodes = node_group.nodes
    links = node_group.links

    nodes.clear()

    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")
    subdivide = nodes.new("GeometryNodeSubdivideMesh")

    input_node.location = (-300,0)
    subdivide.location = (0,0)
    output_node.location = (300,0)

    node_group.inputs.new("NodeSocketGeometry","Geometry")
    node_group.outputs.new("NodeSocketGeometry","Geometry")

    links.new(input_node.outputs["Geometry"], subdivide.inputs["Mesh"])
    links.new(subdivide.outputs["Mesh"], output_node.inputs["Geometry"])


def create_scatter_nodes():

    obj = bpy.context.active_object

    modifier = obj.modifiers.new(name="ScatterNodes", type='NODES')

    node_group = bpy.data.node_groups.new("ScatterNodes", 'GeometryNodeTree')
    modifier.node_group = node_group

    nodes = node_group.nodes
    links = node_group.links

    nodes.clear()

    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")

    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    cube = nodes.new("GeometryNodeMeshCube")

    input_node.location = (-400,0)
    distribute.location = (-150,0)
    instance.location = (150,0)
    cube.location = (0,-200)
    output_node.location = (400,0)

    node_group.inputs.new("NodeSocketGeometry","Geometry")
    node_group.outputs.new("NodeSocketGeometry","Geometry")

    # better density for demo
    distribute.inputs["Density"].default_value = 30

    links.new(input_node.outputs["Geometry"], distribute.inputs["Mesh"])
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(cube.outputs["Mesh"], instance.inputs["Instance"])
    links.new(instance.outputs["Instances"], output_node.inputs["Geometry"])


# ------------------------
# OPERATOR
# ------------------------

class BLENDAGENT_OT_generate(bpy.types.Operator):

    bl_idname = "blendagent.generate"
    bl_label = "Generate"

    def execute(self, context):

        prompt = context.scene.blendagent_prompt.lower()

        plan = get_node_plan(prompt)

        op = str(plan.get("operation", "")).lower()

        print("Prompt:", prompt)
        print("Operation from agent:", op)

        # ---------
        # AI result
        # ---------

        if "subdivide" in op:
            create_subdivide_nodes()

        elif "scatter" in op:
            create_scatter_nodes()

        # ---------
        # fallback using prompt
        # ---------

        elif "scatter" in prompt or "rocks" in prompt:
            print("Fallback scatter triggered")
            create_scatter_nodes()

        elif "subdivide" in prompt or "smooth" in prompt:
            print("Fallback subdivide triggered")
            create_subdivide_nodes()

        else:
            self.report({'WARNING'}, f"Unknown operation: {op}")

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

        layout.prop(scene, "blendagent_prompt")

        layout.operator("blendagent.generate", text="Generate")


# ------------------------
# PROPERTIES
# ------------------------

bpy.types.Scene.blendagent_prompt = bpy.props.StringProperty(
    name="Prompt",
    description="Describe what to generate",
    default="scatter rocks on terrain"
)


# ------------------------
# REGISTER
# ------------------------

def register():

    bpy.utils.register_class(BLENDAGENT_OT_generate)
    bpy.utils.register_class(BLENDAGENT_PT_panel)


def unregister():

    bpy.utils.unregister_class(BLENDAGENT_OT_generate)
    bpy.utils.unregister_class(BLENDAGENT_PT_panel)


if __name__ == "__main__":
    register()