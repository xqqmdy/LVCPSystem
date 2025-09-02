

import bpy
import re
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, IntProperty
from math import radians
from mathutils import Vector
from . import utils


# region Helper Funcs


def _setup_new_lvcp_instance(self, context, name, base_name, set_child_constraints, bone_name, armature_obj=None):
    """Internal function to create a full new LVCP instance."""

    # 1. Create main collection and head origin empty
    coll = utils.create_collection(f"LVCP_{base_name}")
    coll.color_tag = "COLOR_06"
    oo = utils.add_empty(f"Head_Origin_{base_name}", 0.2, "PLAIN_AXES", (0, 0, 0))
    coll.objects.link(oo)
    oo.hide_set(True)
    
    # 2. Add custom properties to collection
    utils.add_custom_prop(coll, utils.Constants.COLLECTION_PROP_O, oo)
    utils.edit_property(coll, utils.Constants.COLLECTION_PROP_O).update(id_type="OBJECT")
    
    # 3. Add custom properties to head origin
    utils.add_custom_prop(oo, utils.Constants.OBJECT_PROP_FRONT, [0.0, 0.0, 0.0])
    utils.add_custom_prop(oo, utils.Constants.OBJECT_PROP_UP, [0.0, 0.0, 0.0])
    
    # 4. Handle parenting constraint
    if set_child_constraints and bone_name:
        arm = armature_obj if armature_obj else context.active_object
        bone = arm.pose.bones.get(bone_name)
        if bone:
            oo.location = arm.matrix_world @ bone.head
            constraint = oo.constraints.new("CHILD_OF")
            constraint.target = arm
            constraint.subtarget = bone_name
        else:
            self.report({"WARNING"}, f"Bone '{bone_name}' not found. Origin not parented.")

    # 5. Create new list item in main PropertyGroup
    lvcp = utils.get_LVCP()
    new_list_item = lvcp.add_list()
    new_list_item.name = name
    new_list_item.collection = coll
    utils.link_collection(lvcp.lvcp_collection, coll, True)
    
    # 6. Create default light group and light empty
    _setup_default_light_group_and_empty(self, context, new_list_item, base_name)
    
    # 7. Set initial drivers for the head
    new_list_item.set_driver_head()
    self.report({"INFO"}, f"Added new LVCP instance: '{name}'")

    return new_list_item



def _setup_default_light_group_and_empty(self, context, lvcp_list_item, base_name):
    """Internal function to create a default light setup for an LVCP instance."""
    lvcp_root = utils.get_LVCP()
    
    # Create Light Group Collection
    group_name = f"LightGroup_{base_name}"
    coll = utils.create_collection(group_name)
    utils.add_custom_prop(coll, utils.Constants.COLLECTION_PROP_MASTER, None)
    utils.edit_property(coll, utils.Constants.COLLECTION_PROP_MASTER).update(id_type="OBJECT")
    utils.link_collection(lvcp_root.light_collection, coll, True)
    
    # Assign group to the LVCP instance
    lvcp_list_item.light_group = coll
    utils.link_collection(lvcp_list_item.collection, coll, True)
    
    # Create Light Master Empty
    master = utils.add_empty(f"Light_Master_{base_name}", 0.5, "PLAIN_AXES", (0, 0, 0))
    lvcp_list_item.collection.objects.link(master)
    master.hide_set(True)
    coll[utils.Constants.COLLECTION_PROP_MASTER] = master
    utils.add_custom_prop(master, utils.Constants.OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
    utils.add_custom_prop(master, "idx", 0)
    utils.edit_property(master, "idx").update(min=0)
    lvcp_list_item.light_master = master
    
    # Create default Light Direction Empty
    empty = utils.add_empty(f"Light_Direction_{base_name}_0", 0.2, "SINGLE_ARROW", (0, 0, 0))
    empty.rotation_euler.x = radians(-90)
    utils.add_custom_prop(empty, utils.Constants.OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
    utils.set_drivers(
        target_context=empty, prop_name=utils.Constants.OBJECT_PROP_LIGHT, # Use constant
        expression="var0", obs=[empty],
        path1="matrix_world", path2="[2]", path3="index"
    )
    lvcp_root.light_collection.objects.link(empty)
    lvcp_list_item.light_group.objects.link(empty)
    
    # Finalize
    lvcp_list_item.update_light_group(context)
    lvcp_list_item.active_light = empty


# region Create Instance


class LVCP_OT_CreateInstance(Operator):
    bl_idname = "lvcp.create_instance"
    bl_label = "Create Instance"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="New LVCP")
    set_child_constraints: BoolProperty(name="Parent to Active Armature Bone", default=False)
    bone_name: StringProperty(name="Bone Name")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        utils.ensure_initial_collections() 

        if self.set_child_constraints and (not context.active_object or context.active_object.type != 'ARMATURE'):
            self.report({"ERROR"}, "To parent, an Armature must be the active object.")
            return {'CANCELLED'}
        _setup_new_lvcp_instance(self, context, self.name, self.name, self.set_child_constraints, self.bone_name)
        return {"FINISHED"}

    def invoke(self, context, _event):
        self.name = context.active_object.name if context.active_object else "New LVCP"
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "set_child_constraints")
        if self.set_child_constraints:
            row = layout.row()
            row.enabled = bool(context.active_object and context.active_object.type == 'ARMATURE')
            row.prop_search(self, "bone_name", context.active_object.data, "bones", text="Bone")


# region Delete Instance


class LVCP_OT_DeleteInstance(Operator):
    bl_idname = "lvcp.delete_instance"
    bl_label = "Delete Instance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_LVCP().list is not None

    def execute(self, context):
        lvcp = utils.get_LVCP()
        list_item = lvcp.list
        if list_item.collection:
            # First remove child collections, then objects, then the parent
            for child in list(list_item.collection.children):
                for obj in list(child.objects): bpy.data.objects.remove(obj)
                bpy.data.collections.remove(child)
            for obj in list(list_item.collection.objects): bpy.data.objects.remove(obj)
            bpy.data.collections.remove(list_item.collection)
        lvcp.remove_list()
        self.report({"INFO"}, f"Deleted LVCP instance.")
        return {"FINISHED"}
    
    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)
        
    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Really delete '{utils.get_LVCP().list.name}' and all its objects?", icon='TRASH')


# region AutoSetup For HSR


class LVCP_OT_AutoSetupForArmature(Operator):
    """Finds a suitable armature and sets up an LVCP instance for its head."""
    bl_idname = "lvcp.auto_setup_for_armature"
    bl_label = "Auto-Setup for Armature"
    bl_options = {"REGISTER", "UNDO"}

    armature_name: StringProperty(name="Armature Name", default="")

    @classmethod
    def poll(cls, context):
        found_armatures = utils.find_suitable_armatures(context)
        return len(found_armatures) > 0

    def execute(self, context):
        utils.ensure_initial_collections()

        arm = None
        found_armatures = utils.find_suitable_armatures(context)
        
        # If armature_name is specified, use it
        if self.armature_name:
            arm = context.scene.objects.get(self.armature_name)
            # Validate the armature
            if not arm:
                self.report({"ERROR"}, f"Armature '{self.armature_name}' not found.")
                return {'CANCELLED'}
            # Check if it matches the pattern and has Head_M bone
            if arm not in found_armatures:
                self.report({"ERROR"}, f"Armature '{self.armature_name}' is not valid for auto-setup.")
                return {'CANCELLED'}
        else:
            # Find the first suitable armature
            if found_armatures:
                arm = found_armatures[0]

        if not arm:
            self.report({"ERROR"}, "No suitable armature found for auto-setup.")
            return {'CANCELLED'}

        armature_name = arm.name
        base_name = utils.get_base_name_from_armature(armature_name)
        
        # Check if an instance already exists for this armature
        lvcp = utils.get_LVCP()
        existing_instance = None
        for item in lvcp.lists:
            if item.collection and item.collection.name == f"LVCP_{base_name}":
                existing_instance = item
                break
                
        if existing_instance:
            self.report({"WARNING"}, f"LVCP instance for '{base_name}' already exists.")
            return {'CANCELLED'}
        
        new_list_item = _setup_new_lvcp_instance(self, context, base_name, base_name, True, "Head_M", armature_obj=arm)
        
        if new_list_item:
            meshes_to_link = []
            target_mesh_names = {"Body", "Face", "Hair"}
            for child in arm.children:
                if child.type == 'MESH':
                    # Check if the mesh name matches target names (with or without numeric suffixes)
                    base_name = child.name.split('.')[0]  # Get the base name without .001, .002, etc.
                    if base_name in target_mesh_names:
                        meshes_to_link.append(child)
            
            if meshes_to_link:
                collection = new_list_item.collection
                for obj in meshes_to_link:
                    utils.add_custom_prop(obj, utils.Constants.OBJECT_PROP_COL, collection)
                    utils.edit_property(obj, utils.Constants.OBJECT_PROP_COL).update(id_type="COLLECTION")
                    obj.data.update()
                self.report({"INFO"}, f"Auto-linked {len(meshes_to_link)} meshes to '{base_name}'.")

        return {"FINISHED"}


# region Link Obj


class LVCP_OT_LinkObjects(Operator):
    bl_idname = "lvcp.link_objects"
    bl_label = "Link Selected"
    bl_description = "Link selected objects to the active LVCP instance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_LVCP().list is not None and context.selected_objects

    def execute(self, context):
        lvcp_list = utils.get_LVCP().list
        collection = lvcp_list.collection

        count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                utils.add_custom_prop(obj, utils.Constants.OBJECT_PROP_COL, collection)
                utils.edit_property(obj, utils.Constants.OBJECT_PROP_COL).update(id_type="COLLECTION")
                obj.data.update()
                count += 1

        self.report({"INFO"}, f"Linked {count} objects to '{lvcp_list.name}'.")
        return {"FINISHED"}


# region Unlink Obj


class LVCP_OT_UnlinkObjects(Operator):
    bl_idname = "lvcp.unlink_objects"
    bl_label = "Unlink Selected"
    bl_description = "Unlink selected objects from the active LVCP instance"
    bl_options = {"REGISTER", "UNDO"}

    obj_name: StringProperty(name="Object Name")

    @classmethod
    def poll(cls, context):
        return context.selected_objects or cls.obj_name

    def execute(self, context):
        lvcp_list = utils.get_LVCP().list

        count = 0
        objects_to_unlink = []
        if self.obj_name:
            obj = bpy.data.objects.get(self.obj_name)
            if obj:
                objects_to_unlink.append(obj)
        else:
            objects_to_unlink = context.selected_objects

        for obj in objects_to_unlink:
            if utils.Constants.OBJECT_PROP_COL in obj:
                del obj[utils.Constants.OBJECT_PROP_COL]
                obj.data.update()
                count += 1

        self.report({"INFO"}, f"Unlinked {count} objects from '{lvcp_list.name}'.")
        return {"FINISHED"}


# region Create Node Groups


class LVCP_OT_CreateNodeGroups(Operator):
    bl_idname = "lvcp.create_node_groups"
    bl_label = "Create Node Groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = utils.get_LVCP()
        if lvcp.head_vector_nodetree and lvcp.light_vector_nodetree:
            self.report({"ERROR"}, "Node groups already exist.")
            return {'CANCELLED'}

        # Light Vector Node
        g_light = bpy.data.node_groups.new(type="ShaderNodeTree", name=utils.Constants.NODE_OUTPUT_LIGHT)
        g_light_out = g_light.nodes.new("NodeGroupOutput")

        g_light.interface.new_socket(utils.Constants.NODE_OUTPUT_LIGHT, in_out="OUTPUT", socket_type="NodeSocketVector")

        attr_path_light = f'["{utils.Constants.OBJECT_PROP_COL}"]["{utils.Constants.COLLECTION_PROP_L}"]["{utils.Constants.OBJECT_PROP_LIGHT}"]'

        ll = utils.add_attribute_node(g_light, attr_path_light, utils.Constants.COLLECTION_PROP_L, "OBJECT")

        g_light.links.new(g_light_out.inputs[utils.Constants.NODE_OUTPUT_LIGHT], ll.outputs["Vector"])

        lvcp.light_vector_nodetree = g_light
        
        # Head Vector Node
        g_head = bpy.data.node_groups.new(type="ShaderNodeTree", name=utils.Constants.HEAD_VECTOR_NODE_NAME)
        g_head_out = g_head.nodes.new("NodeGroupOutput")

        g_head.interface.new_socket(utils.Constants.NODE_OUTPUT_FORWARD, in_out="OUTPUT", socket_type="NodeSocketVector")
        g_head.interface.new_socket(utils.Constants.NODE_OUTPUT_UP, in_out="OUTPUT", socket_type="NodeSocketVector")

        attr_path_forward = f'["{utils.Constants.OBJECT_PROP_COL}"]["{utils.Constants.COLLECTION_PROP_O}"]["{utils.Constants.OBJECT_PROP_FRONT}"]'
        attr_path_up = f'["{utils.Constants.OBJECT_PROP_COL}"]["{utils.Constants.COLLECTION_PROP_O}"]["{utils.Constants.OBJECT_PROP_UP}"]'

        ff = utils.add_attribute_node(g_head, attr_path_forward, "Forward", "OBJECT")
        uu = utils.add_attribute_node(g_head, attr_path_up, "Up", "OBJECT")

        g_head.links.new(g_head_out.inputs[utils.Constants.NODE_OUTPUT_FORWARD], ff.outputs["Vector"])
        g_head.links.new(g_head_out.inputs[utils.Constants.NODE_OUTPUT_UP], uu.outputs["Vector"])

        lvcp.head_vector_nodetree = g_head

        self.report({"INFO"}, "Created Light and Head vector node groups.")
        return {"FINISHED"}


# region Add Node Groups


class LVCP_OT_AddNodeGroupsToMaterial(Operator):
    bl_idname = "lvcp.add_node_groups_to_material"
    bl_label = "Add Nodes to Material"
    bl_options = {"REGISTER", "UNDO"}

    bool_add_light: BoolProperty(name="Light Vector", default=True)
    bool_add_head: BoolProperty(name="Head Vector", default=True)

    @classmethod
    def poll(cls, context):
        return context.area.type == "NODE_EDITOR" and context.area.spaces.active.edit_tree is not None

    def execute(self, context):
        lvcp = utils.get_LVCP()
        node_tree = context.area.spaces.active.edit_tree
        center = utils.get_node_editor_view_center(context)
        
        if self.bool_add_light:
            if lvcp.light_vector_nodetree:
                group_node = node_tree.nodes.new(type="ShaderNodeGroup")
                group_node.node_tree = lvcp.light_vector_nodetree
                group_node.location = center
            else:
                self.report({"WARNING"}, "Light Vector Node Group not found. Please create it first.")

        if self.bool_add_head:
            if lvcp.head_vector_nodetree:
                group_node = node_tree.nodes.new(type="ShaderNodeGroup")
                group_node.node_tree = lvcp.head_vector_nodetree
                group_node.location = center + Vector((250, 0)) if self.bool_add_light else center
            else:
                self.report({"WARNING"}, "Head Vector Node Group not found. Please create it first.")
        return {"FINISHED"}

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)


# region Coll Mgmt


class LVCP_OT_CollectionManager(Operator):
    bl_idname = "lvcp.collection_manager"
    bl_label = "Organize Collections"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = utils.get_LVCP()
        if lvcp.lvcp_collection is None:
            self.report({"ERROR"}, "Main LVCP collection does not exist.")
            return {'CANCELLED'}
        for l in lvcp.lists:
            utils.link_collection(lvcp.lvcp_collection, l.collection, True)
        if lvcp.light_collection:
            utils.link_collection(lvcp.lvcp_collection, lvcp.light_collection, True)
        self.report({"INFO"}, "Organized all LVCP collections.")
        return {"FINISHED"}


# region Select Empty


class LVCP_OT_SelectEmpty(Operator):
    bl_idname = "lvcp.select_empty"
    bl_label = "Select Empty"
    bl_options = {"REGISTER", "UNDO"}
    obj_name: StringProperty()
    def execute(self, context):
        utils.select_object(self.obj_name)
        return {"FINISHED"}


# region Select Linked Obj


class LVCP_OT_SelectObject(Operator):
    bl_idname = "lvcp.select_object"
    bl_label = "Select Linked Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_LVCP().list is not None

    def execute(self, context):
        lvcp_list = utils.get_LVCP().list
        linked_objs = utils.get_objects_with_lvcp(lvcp_list)
        if not linked_objs:
            self.report({"INFO"}, "No objects are linked to this LVCP instance.")
            return {'CANCELLED'}
        for obj in bpy.context.view_layer.objects: obj.select_set(False)
        for obj in linked_objs: obj.select_set(True)
        if linked_objs: bpy.context.view_layer.objects.active = linked_objs[0]
        return {"FINISHED"}


# region Del Node Groups


class LVCP_OT_DeleteNodeGroups(Operator):
    bl_idname = "lvcp.delete_node_groups"
    bl_label = "Delete Node Groups"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = utils.get_LVCP()
        if lvcp.light_vector_nodetree:
            bpy.data.node_groups.remove(lvcp.light_vector_nodetree)
        if lvcp.head_vector_nodetree:
            bpy.data.node_groups.remove(lvcp.head_vector_nodetree)
        self.report({"INFO"}, "Deleted LVCP node groups.")
        return {"FINISHED"}


# region Restore Drivers


class LVCP_OT_RestoreDriver(Operator):
    bl_idname = "lvcp.restore_driver"
    bl_label = "Restore Drivers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.get_LVCP().list is not None

    def execute(self, context):
        lvcp_list = utils.get_LVCP().list
        lvcp_list.update_light_group(context)
        lvcp_list.set_driver_head()
        self.report({"INFO"}, f"Restored drivers for '{lvcp_list.name}'.")
        return {"FINISHED"}


# region Add Light Empty


class LVCP_OT_AddLightEmpty(Operator):
    bl_idname = "lvcp.add_light_empty"
    bl_label = "Add Light Empty"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        lvcp_list = utils.get_LVCP().list
        return lvcp_list and lvcp_list.light_group

    def execute(self, context):
        lvcp_list = utils.get_LVCP().list
        lvcp_root = utils.get_LVCP()
        idx = len(lvcp_list.light_group.objects)
        empty = utils.add_empty(f"Light_Direction_{lvcp_list.name}_{idx}", 0.5, "SINGLE_ARROW", (0, 0, 0))
        empty.rotation_euler.x = radians(-90)
        utils.add_custom_prop(empty, utils.Constants.OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
        utils.set_drivers(
            target_context=empty, prop_name=utils.Constants.OBJECT_PROP_LIGHT,
            expression="var0", obs=[empty],
            path1="matrix_world", path2="[2]", path3="index"
        )
        lvcp_root.light_collection.objects.link(empty)
        lvcp_list.light_group.objects.link(empty)
        lvcp_list.update_light_group(context)
        self.report({"INFO"}, "Added a new light empty.")
        return {"FINISHED"}


# region Registration 


classes = (
    LVCP_OT_CreateInstance,
    LVCP_OT_DeleteInstance,
    LVCP_OT_AutoSetupForArmature,
    LVCP_OT_LinkObjects,
    LVCP_OT_UnlinkObjects,
    LVCP_OT_CreateNodeGroups,
    LVCP_OT_AddNodeGroupsToMaterial,
    LVCP_OT_CollectionManager,
    LVCP_OT_SelectEmpty,
    LVCP_OT_SelectObject,
    LVCP_OT_DeleteNodeGroups,
    LVCP_OT_RestoreDriver,
    LVCP_OT_AddLightEmpty,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)