import bpy
import numpy as np
import mathutils
import math


## A. Set the Object
def load_obj(file_path):
    # Load the .obj file
    bpy.ops.wm.obj_import(filepath=file_path)
    
    # Get the imported object
    obj = bpy.context.selected_objects[0]

    # Create a new material with node system enabled
    material = bpy.data.materials.new(name="VertexEmissionMaterial")
    material.use_nodes = True

    # Clear default nodes
    nodes = material.node_tree.nodes
    for node in nodes:
        nodes.remove(node)
    
    # Create an Emission shader node
    emission_node = nodes.new(type='ShaderNodeEmission')
    emission_node.location = (0, 0)

    # Create a Material Output node
    material_output = nodes.new(type='ShaderNodeOutputMaterial')
    material_output.location = (400, 0)
    
    # Connect the emission node to the output
    material.node_tree.links.new(emission_node.outputs['Emission'], material_output.inputs['Surface'])

    # Create a Vertex Color node
    vertex_color_node = nodes.new(type='ShaderNodeVertexColor')
    vertex_color_node.location = (-300, 0)

    # Link vertex color to the emission color
    material.node_tree.links.new(vertex_color_node.outputs['Color'], emission_node.inputs['Color'])

    obj.data.materials.append(material)

def add_camera():
    # Get the camera or create one if not found
    cam = bpy.data.objects.get('Camera')
    if not cam:
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
    bpy.context.scene.camera = cam

    # Set camera properties
    cam.data.clip_start = 0.001
    cam.data.lens_unit = 'FOV'
    cam.data.angle = 54.22 * (3.14159 / 180)  # Convert degrees to radians
    
    # Set the resolution for render output
    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 512

def set_camera(extrinsic_matrix):
    # Get the active camera in the scene
    camera = bpy.context.scene.camera

    # Convert the numpy array to a Blender-compatible matrix
    blender_matrix = mathutils.Matrix(extrinsic_matrix)

    # Set the camera's matrix_world to the new extrinsic matrix
    camera.matrix_world = blender_matrix

    # Convert 180 degrees to radians
    rotation_y = math.radians(180)

    # Add 180 degrees to the existing Y rotation
    camera.rotation_euler[1] += rotation_y

def set_keyframe(c2w_start, c2w_end):
    # Set camera properties at the start
    set_camera(c2w_start)
    
    # Insert keyframe for the start at frame 1
    bpy.context.scene.frame_set(1)  # Set the current frame to 1
    camera = bpy.data.objects['Camera']
    
    # Insert keyframes for camera properties at frame 1
    camera.keyframe_insert(data_path="location", frame=1)  # Keyframe for location
    camera.keyframe_insert(data_path="rotation_euler", frame=1)  # Keyframe for rotation
    camera.data.keyframe_insert(data_path="lens", frame=1)  # Keyframe for lens (FOV)
    
    # Insert keyframe for the end at frame 24
    bpy.context.scene.frame_set(24)  # Set the current frame to 24
    camera = bpy.data.objects['Camera']
    
    # Set camera properties at the end
    set_camera(c2w_end)
    
    # Insert keyframes for camera properties at frame 24
    camera.keyframe_insert(data_path="location", frame=24)  # Keyframe for location
    camera.keyframe_insert(data_path="rotation_euler", frame=24)  # Keyframe for rotation
    camera.data.keyframe_insert(data_path="lens", frame=24)  # Keyframe for lens (FOV)
    




path = "/Users/zhangzhiyuan/Desktop/quick develop/output/rot_left/full_mesh.obj"
load_obj(path)
add_camera()

c2w_start = np.array([[-1.,  0.,  0.,  0.],
        [ 0.,  0.,  1.,  0.],
        [ 0.,  1.,  0.,  0.],
        [ 0.,  0.,  0.,  1.]])

c2w_end = np.array([[    -0.9960,      0.0000,      0.0899,      0.0005],
        [     0.0899,      0.0000,      0.9960,      0.0084],
        [     0.0000,      1.0000,      0.0000,      0.0000],
        [     0.0000,      0.0000,      0.0000,      1.0000]])
set_keyframe(c2w_start, c2w_end)