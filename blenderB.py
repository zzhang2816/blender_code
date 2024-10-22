import bpy
import os

class UndoAfterExecution:
    """ Reverts all changes done to the blender project inside this block.

    Usage: with UndoAfterExecution():
    """
    def __init__(self):
        pass
    
    def __enter__(self):
        # Create an undo snapshot
        bpy.ops.ed.undo_push(message="Entering UndoAfterExecution block")
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        # Revert all changes done during the block
        bpy.ops.ed.undo()
        if exc_type:
            print(f"Exception occurred: {exc_value}")
        return False


class RendererUtility():
    @staticmethod
    def output_vector_field(forward_flow: bool, backward_flow: bool, output_dir: str, filename: str = ""):
        """ Configures compositor to output speed vectors.

        :param forward_flow: Whether to render forward optical flow.
        :param backward_flow: Whether to render backward optical flow.
        :param output_dir: The directory to write images to.
        """

        # Flow settings (is called "vector" in blender)
        bpy.context.scene.render.use_compositing = True
        bpy.context.scene.use_nodes = True
        bpy.context.view_layer.use_pass_vector = True

        # Adapt compositor to output vector field
        tree = bpy.context.scene.node_tree
        links = tree.links
        
        # clear default nodes
        for n in tree.nodes:
            tree.nodes.remove(n)

        # render node
        render_layer_node = tree.nodes.new('CompositorNodeRLayers')

        separate_rgba = tree.nodes.new('CompositorNodeSepRGBA')
        links.new(render_layer_node.outputs['Vector'], separate_rgba.inputs['Image'])

        if forward_flow:
            combine_fwd_flow = tree.nodes.new('CompositorNodeCombRGBA')
            links.new(separate_rgba.outputs['B'], combine_fwd_flow.inputs['R'])
            links.new(separate_rgba.outputs['A'], combine_fwd_flow.inputs['G'])
            fwd_flow_output_file = tree.nodes.new('CompositorNodeOutputFile')
            fwd_flow_output_file.base_path = output_dir
            fwd_flow_output_file.format.file_format = "OPEN_EXR"
            fwd_flow_output_file.file_slots.values()[0].path = f"fwd_flow_{filename}"
            links.new(combine_fwd_flow.outputs['Image'], fwd_flow_output_file.inputs['Image'])

        if backward_flow:
            # actually need to split - otherwise the A channel of the image is getting weird, no idea why
            combine_bwd_flow = tree.nodes.new('CompositorNodeCombRGBA')
            links.new(separate_rgba.outputs['R'], combine_bwd_flow.inputs['R'])
            links.new(separate_rgba.outputs['G'], combine_bwd_flow.inputs['G'])
            bwd_flow_output_file = tree.nodes.new('CompositorNodeOutputFile')
            bwd_flow_output_file.base_path = output_dir
            bwd_flow_output_file.format.file_format = "OPEN_EXR"
            bwd_flow_output_file.file_slots.values()[0].path = f"bwd_flow_{filename}"
            links.new(combine_bwd_flow.outputs['Image'], bwd_flow_output_file.inputs['Image'])

    @staticmethod
    def output_depth(from_max, output_dir: str):
        # Flow settings (is called "vector" in blender)
        bpy.context.scene.render.use_compositing = True
        bpy.context.scene.use_nodes = True
        bpy.context.scene.view_layers["ViewLayer"].use_pass_z = True

        # Adapt compositor to output vector field
        tree = bpy.context.scene.node_tree
        links = tree.links
        
        # clear default nodes
        for n in tree.nodes:
            tree.nodes.remove(n)

        # render node
        render_layer_node = tree.nodes.new('CompositorNodeRLayers')
        
        # Map_range node
        map = tree.nodes.new(type="CompositorNodeMapRange")
        map.inputs['From Max'].default_value = from_max
        links.new(render_layer_node.outputs['Depth'], map.inputs['Value'])
        
        # invert node
        invert = tree.nodes.new('CompositorNodeInvert')
        links.new(map.outputs['Value'], invert.inputs['Color'])

        # file_output node
        fileOutput = tree.nodes.new(type="CompositorNodeOutputFile")
        fileOutput.base_path = output_dir
        fileOutput.file_slots.values()[0].path = "depth_"
        links.new(invert.outputs['Color'], fileOutput.inputs['Image'])


class Render_task():
    @staticmethod
    def render_next_frame(cls):
        scene = bpy.context.scene
        if cls.frame_current <= scene.frame_end:
            scene.frame_set(cls.frame_current)
            bpy.ops.render.render(write_still=True)
            if cls.frame_current == scene.frame_end:
                cls.curr_task_finish = True
            cls.frame_current += 1
        cls.rendering = False


class Depth_task(Render_task):
    @staticmethod
    def set_rendering(cls):
        cls.curr_task_finish = False
        scene = bpy.context.scene
        from_max = bpy.data.objects['Camera'].data.clip_end + 5
        
        scene.render.filepath = os.path.join(cls.fp,"tmp")
        RendererUtility.output_depth(from_max, cls.depth_dir)

    @staticmethod
    def clear_rendering():
        # clear the nodes
        tree = bpy.context.scene.node_tree
        
        for n in tree.nodes:
            tree.nodes.remove(n)


class Optical_task(Render_task):
    @staticmethod
    def set_rendering(cls):
        cls.curr_task_finish = False
        scene = bpy.context.scene
        optical_dir = os.path.join(cls.optical_dir, "all")

        scene.render.filepath = os.path.join(cls.fp, "tmp")
        RendererUtility.output_vector_field(True, True, optical_dir)
    
    @staticmethod
    def clear_rendering():
        # clear the nodes
        tree = bpy.context.scene.node_tree
        
        for n in tree.nodes:
            tree.nodes.remove(n)


class Optical_scheduled_task_fwd():
    @staticmethod
    def set_rendering(cls):
        cls.curr_task_finish = False
        scene = bpy.context.scene
        scene.render.filepath = os.path.join(cls.fp,"tmp")
        
        cls.render_queue = []
        
        frame_start = bpy.context.scene.frame_start
        frame_end = bpy.context.scene.frame_end
        interval_length = cls.interval_length
        idx_arr = [frame_start] + [i for i in range(frame_start+interval_length-1, frame_end+1, interval_length)]
        
        for i in range(0, len(idx_arr)-1):
            frame_left = idx_arr[i]
            frame_right = idx_arr[i+1]
            output_dir = os.path.join(cls.fp, f"{frame_left}_{frame_right}")
            
            for j in range(frame_left + 1, frame_right):
                cls.render_queue.append({
                    "output_dir": output_dir,
                    "frame_left": frame_left,
                    "j": j
                })
                cls.render_queue.append({
                    "output_dir": output_dir,
                    "frame_right": frame_right,
                    "j": j
                })
                
    @staticmethod
    def render_next_frame(cls):
        if len(cls.render_queue) >= 0:
            q_item = cls.render_queue.pop(0)
            output_dir, j = q_item["output_dir"], q_item["j"]
            obj = bpy.data.collections['Collection'].objects['Armature']
            scene = bpy.context.scene
            scene.render.filepath = os.path.join(cls.fp,"tmp")
            
            with UndoAfterExecution():
                if "frame_left" in q_item:
                    frame_left = q_item["frame_left"]
                
                    # Move the keyframes
                    if j != frame_left + 1:
                        delete_keyframe(obj, frame_left + 1)
                        insert_keyframe(obj, j, frame_left + 1)
                    
                    # Set up composition nodes (bwd)
                    RendererUtility.output_vector_field(False, True, output_dir, f"{j}_")
                    scene.frame_set(frame_left + 1)
                    bpy.ops.render.render(write_still=True)
                    
                    # Set up composition nodes (fwd)
                    RendererUtility.output_vector_field(True, False, output_dir, f"{j}_")
                    scene.frame_set(frame_left)
                    bpy.ops.render.render(write_still=True)
                    
                elif "frame_right" in q_item:
                    frame_right = q_item["frame_right"]
                
                    # Move the keyframes
                    if j != frame_right - 1:
                        delete_keyframe(obj, frame_right - 1)
                        insert_keyframe(obj, j, frame_right - 1)
                        
                    # Set up composition nodes (bwd)
                    RendererUtility.output_vector_field(False, True, output_dir, f"{j}_")
                    scene.frame_set(frame_right)
                    bpy.ops.render.render(write_still=True)
                    
                    # Set up composition nodes (fwd)
                    RendererUtility.output_vector_field(True, False, output_dir, f"{j}_")
                    scene.frame_set(frame_right-1)
                    bpy.ops.render.render(write_still=True)
                
            if len(cls.render_queue) == 0:
                cls.curr_task_finish = True
                
        cls.rendering = False
    
    @staticmethod
    def clear_rendering():
        tree = bpy.context.scene.node_tree
        
        for n in tree.nodes:
            tree.nodes.remove(n)


class ViewPort_task():
    @staticmethod
    def set_rendering(cls):
        cls.curr_task_finish = False
        # Set the context to the active view
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.shading.type = 'MATERIAL'
                break

        # Enable transparent background
        bpy.context.scene.render.film_transparent = True

        # Set the output format to PNG with RGBA (for transparency)
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'

        bpy.context.scene.render.filepath = cls.ani_dir

        # Hide all non-mesh objects in the viewport
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                obj.hide_viewport = True 

    @staticmethod
    def clear_rendering():
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                obj.hide_viewport = False
           
    @staticmethod     
    def render_next_frame(cls):
        scene = bpy.context.scene
        if cls.frame_current <= scene.frame_end:
            scene.frame_set(cls.frame_current)
            bpy.context.scene.render.filepath = os.path.join(cls.ani_dir, f"{cls.frame_current:04d}.png")
            bpy.ops.render.opengl(write_still=True, view_context=True) # this line is modified
            if cls.frame_current == scene.frame_end:
                cls.curr_task_finish = True
            cls.frame_current += 1
        cls.rendering = False
        
        
def delete_keyframe(obj, frame):
    """
    Delete the keyframe at a specific frame.
    
    Args:
        obj: The object whose keyframes will be deleted.
        frame: The frame number where the keyframe will be deleted.
    """
    fcurves = obj.animation_data.action.fcurves
    for fcurve in fcurves:
        keyframe_points = fcurve.keyframe_points
        for keyframe in keyframe_points:
            if keyframe.co.x == frame:
                keyframe_points.remove(keyframe)
                break


def insert_keyframe(obj, frame_from, frame_to):
    """
    Insert a keyframe from frame_from into frame_to.
    
    Args:
        obj: The object whose keyframes will be inserted.
        frame_from: The frame number to copy the keyframe from.
        frame_to: The frame number to insert the keyframe to.
    """
    fcurves = obj.animation_data.action.fcurves
    for fcurve in fcurves:
        # Find the keyframe at frame_from
        keyframe_from = None
        for keyframe in fcurve.keyframe_points:
            if keyframe.co.x == frame_from:
                keyframe_from = keyframe
                break
        
        # Insert the keyframe at frame_to with the same value
        if keyframe_from:
            fcurve.keyframe_points.insert(frame_to, keyframe_from.co.y)


class RenderEssentials(bpy.types.Operator):
    bl_idname = "render.video_scupluting"
    bl_label = "Render Essentials"
    
    fp = "//new_folder1"
    ani_dir = os.path.join(fp, "ani")
    depth_dir = os.path.join(fp, "depth")
    optical_dir = os.path.join(fp, "optical")
    rendering_tasks = None
    curr_task_finish = True
    current_task = None
    interval_length = 8
        
    def execute(self, context):        
        self.rendering = False
        # self.rendering_tasks = [ViewPort_task(), Depth_task(), Optical_task()]
        self.rendering_tasks = [ViewPort_task(), Depth_task()]
        
        # Lock interface
        bpy.types.RenderSettings.use_lock_interface = True
        
        # Create timer event that runs every second to check if render render_queue needs to be updated
        self.timer_event = context.window_manager.event_timer_add(0.5, window=context.window)
        
        # register this as running in background
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}

            
    def modal(self, context, event):
        # ESC
        if event.type == 'ESC':
            bpy.types.RenderSettings.use_lock_interface = False
            print('CANCELLED')
            return {'CANCELLED'}

        # timer event every second
        elif event.type == 'TIMER':
            if len(self.rendering_tasks) == 0 and self.curr_task_finish:
                context.window_manager.event_timer_remove(self.timer_event)
                bpy.types.RenderSettings.use_lock_interface = False
                print('FINISHED')
                return {"FINISHED"}
            
            elif self.rendering is False:
                self.rendering = True
                if self.curr_task_finish:
                    if self.current_task != None:
                        self.current_task.clear_rendering()
                    self.current_task = self.rendering_tasks.pop(0)
                    self.current_task.set_rendering(self)
                    self.frame_current = bpy.context.scene.frame_start
                self.current_task.render_next_frame(self)

        return {'PASS_THROUGH'}
     
    
def register():
    bpy.utils.register_class(RenderEssentials)
    
def unregister():
    bpy.utils.unregister_class(RenderEssentials)

if __name__ == "__main__":
    register()
    bpy.ops.render.video_scupluting()