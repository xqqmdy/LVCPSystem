bl_info = {
    "name": "LVCPSystem",
    "description": "Light Vector and Head Vector Management System",
    "author": "Nifs/Pulse",
    "version": (0, 0, 2),
    "blender": (4, 0, 0),
    "location": "View3D",
    "warning": "Dev ver.",
    "wiki_url": "",
    "tracker_url": "https://github.com/Puls-r/LVCPSystem/issues",
    "wiki_url": "https://github.com/Puls-r/LVCPSystem",
    "category": "Object",
}


import bpy
from bpy.types import Operator, Panel, UIList, PropertyGroup, Collection, NodeTree, Scene
from bpy.props import StringProperty, BoolProperty, IntProperty, PointerProperty, CollectionProperty
from mathutils import Vector


##Names##
COLLECTION_PROP_L = "LL"
COLLECTION_PROP_F = "FF"
COLLECTION_PROP_U = "UU"
COLLECTION_PROP_O = "OO"
OBJECT_PROP_COL = "lvcp"
OBJECT_PROP_LIGHT = "matrix_light"
OBJECT_PROP_FRONT = "matrix_front"
OBJECT_PROP_UP = "matrix_up"
NODE_OUTPUT_LIGHT = "Light_Vector"
NODE_OUTPUT_FORWARD = "Forward_Vector"
NODE_OUTPUT_UP = "Up_Vector"


###LVCP Utils###
def get_LVCP():
    return bpy.context.scene.LVCP


def get_LVCP_Lights_Collections():
    return bpy.context.scene.LVCP.light_collection


def get_blender_version():
    return bpy.app.version


def add_empty(self, context, name, size, type, location):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_size = size
    empty.empty_display_type = type
    empty.location = location
    return empty


def create_collection(name):
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def search_area(type):
    for area in bpy.context.screen.areas:
        if area.type == type:
            return area


def node_center(node_tree):
    min_x = 100000.0
    max_x = -100000.0
    min_y = 100000.0
    max_y = -100000.0
    nodes = node_tree.nodes
    for node in nodes:
        (x, y) = node.location
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y

    mid_x = (max_x + min_x) / 2
    mid_y = (max_y + min_y) / 2

    for node in nodes:
        (x, y) = node.location
        new_loc = (x - mid_x, y - mid_y)
        node.location = new_loc


###node###


def add_attribute_node(node_tree, name, label, type="OBJECT"):
    attrnode = node_tree.nodes.new(type="ShaderNodeAttribute")
    attrnode.attribute_name = name
    attrnode.label = label
    attrnode.attribute_type = type
    return attrnode


def make_light_vector_node(driver_mode=False):
    g = bpy.data.node_groups.new(type="ShaderNodeTree", name=NODE_OUTPUT_LIGHT)
    g_out = g.nodes.new("NodeGroupOutput")
    g.interface.new_socket(NODE_OUTPUT_LIGHT, in_out="OUTPUT", socket_type="NodeSocketVector")
    if driver_mode:
        ll = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_L}"]["{OBJECT_PROP_LIGHT}"]', COLLECTION_PROP_L, "OBJECT")
        g.links.new(g_out.inputs[NODE_OUTPUT_LIGHT], ll.outputs["Vector"])
    else:
        ll = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_L}"].rotation_euler', COLLECTION_PROP_L, "OBJECT")
        g.links.new(g_out.inputs[NODE_OUTPUT_LIGHT], ll.outputs["Vector"])
    return g


def make_head_vector_node(driver_mode=False):
    g = bpy.data.node_groups.new(type="ShaderNodeTree", name=f"Head_Vector")
    g_out = g.nodes.new("NodeGroupOutput")
    g.interface.new_socket(NODE_OUTPUT_FORWARD, in_out="OUTPUT", socket_type="NodeSocketVector")
    g.interface.new_socket(NODE_OUTPUT_UP, in_out="OUTPUT", socket_type="NodeSocketVector")
    ff, uu, oo = None, None, None
    if driver_mode:
        ff = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_O}"]["{OBJECT_PROP_FRONT}"]', COLLECTION_PROP_F, "OBJECT")
        uu = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_O}"]["{OBJECT_PROP_UP}"]', COLLECTION_PROP_U, "OBJECT")
        g.links.new(g_out.inputs[NODE_OUTPUT_FORWARD], ff.outputs["Vector"])
        g.links.new(g_out.inputs[NODE_OUTPUT_UP], uu.outputs["Vector"])
    else:
        ff = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_F}"].location', COLLECTION_PROP_F, "OBJECT")
        uu = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_U}"].location', COLLECTION_PROP_U, "OBJECT")
        oo = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_O}"].location', COLLECTION_PROP_O, "OBJECT")
        vec_subForward = g.nodes.new(type="ShaderNodeVectorMath")
        vec_subForward.operation = "SUBTRACT"
        vec_subUp = g.nodes.new(type="ShaderNodeVectorMath")
        vec_subUp.operation = "SUBTRACT"
        g.links.new(vec_subForward.inputs[0], ff.outputs[0])
        g.links.new(vec_subForward.inputs[1], oo.outputs[0])
        g.links.new(vec_subUp.inputs[0], uu.outputs[0])
        g.links.new(vec_subUp.inputs[1], oo.outputs[0])
        g.links.new(g_out.inputs[NODE_OUTPUT_FORWARD], vec_subForward.outputs["Vector"])
        g.links.new(g_out.inputs[NODE_OUTPUT_UP], vec_subUp.outputs["Vector"])
    return g


def make_group_node(self, context, driver_mode):
    lvcp = get_LVCP()
    if lvcp.head_vector_nodetree and lvcp.light_vector_nodetree:
        self.report({"ERROR"}, "Already added Node Group")
    if lvcp.head_vector_nodetree is None:
        lvcp.head_vector_nodetree = make_head_vector_node(driver_mode)
    if lvcp.light_vector_nodetree is None:
        lvcp.light_vector_nodetree = make_light_vector_node(driver_mode)
    return {"FINISHED"}


def add_l_or_h_group_node(self, context, l, h):
    lvcp = get_LVCP()
    area = context.area
    if area:
        node_tree = area.spaces.active.edit_tree
        if node_tree is None:
            self.report({"ERROR"}, "Not found NodeGroup in area")
            return
        if l:
            g = lvcp.light_vector_nodetree
            if g:
                group_node = node_tree.nodes.new(type="ShaderNodeGroup")
                group_node.node_tree = g
                self.report({"INFO"}, "Light Vector Node Group Added")
            else:
                self.report({"ERROR"}, "Not found Light Vector Node Group")
        if h:
            g = lvcp.head_vector_nodetree
            if g:
                group_node = node_tree.nodes.new(type="ShaderNodeGroup")
                group_node.node_tree = lvcp.head_vector_nodetree
                group_node.location = group_node.location + Vector((0, -200))
                self.report({"INFO"}, "Head Vector Node Group Added")
            else:
                self.report({"ERROR"}, "Not found Head Vector Node Group")
    else:
        self.report({"ERROR"}, "Not found NodeGroup in area")
        return
    return {"FINISHED"}


###Properties###
def edit_property(target_context, property_name, description, id_type):
    ui = target_context.id_properties_ui(property_name)
    ui.update(description=description, id_type=id_type)
    return ui


def add_custom_prop(target_context, prop_name, obj):
    target_context[prop_name] = obj


def set_drivers(target_context, prop_name, expression, obs, driver_type="SINGLE_PROP", path1=None, path2=None, path3=None):
    prop_data_path = f'["{prop_name}"]'
    fcurve = target_context.driver_add(prop_data_path)
    if isinstance(fcurve, list):
        for i, driver in enumerate(fcurve):
            driver.driver.expression = expression
            for idx, v in enumerate(obs):
                var = driver.driver.variables.new()
                var.name = f"var{idx}"
                var.type = driver_type
                var.targets[0].id = v
                if path1:
                    path = path1
                    path += f"[{i}]" if path2 == "index" else path2
                    path += f"[{i}]" if path3 == "index" else path3
                    var.targets[0].data_path = path
                else:
                    var.targets[0].transform_type = "LOC" + ["_X", "_Y", "_Z"][i]
                    var.targets[0].transform_space = "WORLD_SPACE"
    return fcurve


def add_prop_and_empty(self, context, name, add_light, set_child_constraints, bone_name, driver_mode):
    coll = create_collection(f"LVCP_{name}")
    target_context = coll

    coll.color_tag = "COLOR_06"

    # create empty objects
    oo = add_empty(self, context, "Head_Origin", 0.5, "PLAIN_AXES", (0, 0, 0))  # Head Origin
    ff = add_empty(self, context, "Head_Forward", 0.1, "CUBE", (0, -1, 0))  # Head Forward
    uu = add_empty(self, context, "Head_Up", 0.1, "CUBE", (0, 0, 1))  # Head Up

    # prepare custom properties
    add_custom_prop(target_context, COLLECTION_PROP_L, None)
    add_custom_prop(target_context, COLLECTION_PROP_O, oo)
    add_custom_prop(target_context, COLLECTION_PROP_F, ff)
    add_custom_prop(target_context, COLLECTION_PROP_U, uu)

    edit_property(target_context, COLLECTION_PROP_L, "LVCP", "OBJECT")
    edit_property(target_context, COLLECTION_PROP_F, "LVCP", "OBJECT")
    edit_property(target_context, COLLECTION_PROP_U, "LVCP", "OBJECT")
    edit_property(target_context, COLLECTION_PROP_O, "LVCP", "OBJECT")

    # add objects to collection
    coll.objects.link(oo)
    coll.objects.link(ff)
    coll.objects.link(uu)

    # parent
    ff.parent = oo
    uu.parent = oo
    if driver_mode:
        add_custom_prop(oo, OBJECT_PROP_FRONT, [0.0, 0.0, 0.0])
        add_custom_prop(oo, OBJECT_PROP_UP, [0.0, 0.0, 0.0])
        set_drivers(target_context=oo, prop_name=OBJECT_PROP_FRONT, expression="var1-var0", obs=[oo, ff], driver_type="TRANSFORMS")
        set_drivers(target_context=oo, prop_name=OBJECT_PROP_UP, expression="var1-var0", obs=[oo, uu], driver_type="TRANSFORMS")
    # create light object
    if add_light:
        l_coll = get_LVCP().light_collection
        ll = add_empty(self, context, "Light_Direction", 0.5, "SINGLE_ARROW", (0, 0, 0))  # Light Direction
        target_context[COLLECTION_PROP_L] = ll
        l_coll.objects.link(ll)
        light = bpy.data.lights.new("Sun", "SUN")
        light_obj = bpy.data.objects.new("Sun", light)
        light_obj.location = (0, 0, 0)
        light_obj.rotation_euler = (0, -3.14, 0)
        l_coll.objects.link(light_obj)
        light_obj.parent = ll
        if driver_mode:
            add_custom_prop(ll, OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
            set_drivers(
                target_context=ll,
                prop_name=OBJECT_PROP_LIGHT,
                expression="var0",
                obs=[light_obj],
                path1="matrix_world",
                path2="[2]",
                path3="index",
            )
    if set_child_constraints:
        if bone_name:
            arm = bpy.context.active_object
            bone = arm.data.bones.get(bone_name)
            if bone:
                bone_name = bone.name
                bone = arm.pose.bones.get(bone_name)
                if bone:
                    oo.location = bone.id_data.matrix_world @ bone.head
                    oo.constraints.new("CHILD_OF")
                    oo.constraints["Child Of"].target = arm
                    oo.constraints["Child Of"].subtarget = bone_name
                else:
                    self.report({"ERROR"}, "Not found Bone")

    lvcp = get_LVCP()
    new = lvcp.add_list()
    lvcp.idx = len(lvcp.lists) - 1
    new.name = name
    new.collection = coll
    self.report({"INFO"}, "Added Prop and Empty")


def del_prop_and_empty(self, context, bool_del_light, bool_del_lgiht_vector_node, bool_del_head_vector_node):
    lvcp = get_LVCP()
    coll = lvcp.collection
    lgiht = coll[COLLECTION_PROP_L]
    coll[COLLECTION_PROP_L] = None
    objs = coll.objects
    lvn = lvcp.light_vector_node
    hvn = lvcp.head_vector_node
    if objs:
        for obj in objs:
            bpy.data.objects.remove(obj)
        bpy.data.collections.remove(coll)
        get_LVCP().remove_list()
        self.report({"INFO"}, "Deleted Prop and Empty")
    else:
        self.report({"ERROR"}, "Not found Prop and Empty")
    if bool_del_light:
        if lgiht:
            bpy.data.objects.remove(lgiht)
        else:
            self.report({"ERROR"}, "Not found Light Object")

    if bool_del_lgiht_vector_node:
        if lvn:
            bpy.data.node_groups.remove(lvn)
        else:
            self.report({"ERROR"}, "Not found Light Vector Node")

    if bool_del_head_vector_node:
        if hvn:
            bpy.data.node_groups.remove(hvn)
        else:
            self.report({"ERROR"}, "Not found Head Vector Node")


def set_prop_to_objcts(self, context):
    objs = bpy.context.selected_objects
    lvcp = get_LVCP().list
    collection = lvcp.collection
    for obj in objs:
        add_custom_prop(obj, OBJECT_PROP_COL, collection)
        edit_property(obj, OBJECT_PROP_COL, "LVCP", "COLLECTION")
        obj.data.update()
    self.report({"INFO"}, "Added Prop to Objects")


def has_lvcp(obj, lvcp):
    if OBJECT_PROP_COL in obj and obj[OBJECT_PROP_COL] == lvcp.collection:
        return True
    return False


def get_objects_with_lvcp(self, context, item):
    objs = bpy.context.scene.objects
    lo = []
    for obj in objs:
        if has_lvcp(obj, item):
            lo.append(obj)
    return lo


def select_object(self, context, obj):
    bpy.context.view_layer.objects.active = bpy.data.objects[obj]
    bpy.data.objects[obj].select_set(True)


class LVCP_OT_AddPropAndEmpty(Operator):
    bl_idname = "lvcp.add_prop_and_empty_only"
    bl_label = "Add Prop And Empty Only"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(default="")  # type: ignore
    bool_add_light: BoolProperty(name="Add Light", default=True)  # type: ignore
    bool_set_child_constants: BoolProperty(name="Set Child Constants", default=True)  # type: ignore
    bone_name: StringProperty(default="")  # type: ignore
    bool_driver_mode: BoolProperty(default=True)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context):
        add_prop_and_empty(
            self, context, self.name, self.bool_add_light, self.bool_set_child_constants, self.bone_name, self.bool_driver_mode
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        self.name = bpy.context.active_object.name
        layout.prop(self, "name")
        layout.prop(self, "bool_add_light")
        if bpy.context.active_object.type == "ARMATURE":
            layout.label(text="When you set child constants, please select bone.")
            layout.prop(self, "bool_set_child_constants")
            layout.prop_search(self, "bone_name", bpy.context.active_object.data, "bones", text="Bone")
        layout.prop(self, "bool_driver_mode", text="Driver Mode")


class LVCP_OT_DelPropAndEmpty(Operator):
    bl_idname = "lvcp.del_prop_and_empty_only"
    bl_label = "Del Prop And Empty Only"
    bl_options = {"REGISTER", "UNDO"}

    bool_del_light: BoolProperty(default=False)  # type: ignore
    bool_del_lgiht_vector_node: BoolProperty(default=False)  # type: ignore
    bool_del_head_vector_node: BoolProperty(default=False)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context):
        del_prop_and_empty(self, context, self.bool_del_light, self.bool_del_lgiht_vector_node, self.bool_del_head_vector_node)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        lvcp = get_LVCP().list
        layout = self.layout
        layout.label(text=f"Delete {lvcp.name}?")
        layout.prop(self, "bool_del_light")
        layout.prop(self, "bool_del_lgiht_vector_node")
        layout.prop(self, "bool_del_head_vector_node")


class LVCP_OT_SetPropToObject(Operator):
    bl_idname = "lvcp.set_prop_to_objects"
    bl_label = "Set Prop To Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context):
        if get_LVCP().list is None:
            self.report({"ERROR"}, "Not found LVCP")
            return
        set_prop_to_objcts(self, context)
        return {"FINISHED"}


class LVCP_OT_DelPropFromObjects(Operator):
    bl_idname = "lvcp.del_prop_from_objects"
    bl_label = "Del Prop From Objects"
    bl_options = {"REGISTER", "UNDO"}

    def _del_prop_from_objcts(self, objs):
        for obj in objs:
            if OBJECT_PROP_COL in obj:
                del obj[OBJECT_PROP_COL]
            obj.data.update()
        self.report({"INFO"}, "Deleted Prop from Objects")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context):
        objs = bpy.context.selected_objects
        self._del_prop_from_objcts(objs)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Delete Prop from Selected Objects?")


class LVCP_OT_MakeGroupNode(Operator):
    bl_idname = "lvcp.make_group_node"
    bl_label = "Make Group Node"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Make Group Node"

    driver_mode: BoolProperty(default=True)  # type: ignore

    def execute(self, context):
        make_group_node(self, context, self.driver_mode)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "driver_mode")


class LVCP_OT_AddGroupNode(Operator):
    bl_idname = "lvcp.add_group_node"
    bl_label = "Add Group Node"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Add Group Node"

    bool_add_light: BoolProperty(name="Add Light", default=True)  # type: ignore
    bool_add_head: BoolProperty(name="Add Head", default=True)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.area.type == "NODE_EDITOR" and context.area.spaces.active.edit_tree is not None

    def execute(self, context):
        add_l_or_h_group_node(self, context, self.bool_add_light, self.bool_add_head)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bool_add_light")
        layout.prop(self, "bool_add_head")


class LVCP_OT_MakeLightCollection(Operator):
    bl_idname = "lvcp.make_light_collection"
    bl_label = "Make Light Collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        coll = create_collection("Lights")
        get_LVCP().light_collection = coll
        return {"FINISHED"}


class LVCP_OT_MakeLVCPCollection(Operator):
    bl_idname = "lvcp.make_lvcp_collection"
    bl_label = "Make LVCP Collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        coll = create_collection("LVCP")
        get_LVCP().lvcp_collection = coll
        return {"FINISHED"}


class LVCP_OT_CollectionManager(Operator):
    bl_idname = "lvcp.collection_manager"
    bl_label = "Collection Manager"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Move collections to LVCP Collection"

    bool_unlink: BoolProperty(name="Unlink", default=False)  # type: ignore

    def _collection_manager(self, context, unlink=False):
        lvcp = get_LVCP()
        if lvcp.lvcp_collection is None:
            lvcp.lvcp_collection = create_collection("LVCP")
        for l in lvcp.lists:
            c = l.collection
            if c.name not in [child.name for child in lvcp.lvcp_collection.children]:
                if unlink:
                    bpy.context.scene.collection.children.unlink(c)
                lvcp.lvcp_collection.children.link(c)
        c = lvcp.light_collection
        if c.name not in [child.name for child in lvcp.lvcp_collection.children]:
            if unlink:
                bpy.context.scene.collection.children.unlink(c)
            lvcp.lvcp_collection.children.link(c)
        self.report({"INFO"}, "Managed Collections")

    def execute(self, context):
        self._collection_manager(context, self.bool_unlink)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "bool_unlink", text="Unlink Collections From Current Collection")


class LVCP_OT_RestoreCollection(Operator):
    bl_idname = "lvcp.restore_collection"
    bl_label = "Restore Collection"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Restore from collections with FF, OO, UU and LL properties"

    collection_name: StringProperty(name="Collection")  # type: ignore

    def _restore_collection(self, context, collection_name):
        lvcp = get_LVCP()
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            self.report({"ERROR"}, "Not found Collection")
        if (
            collection.get(COLLECTION_PROP_L)
            and collection.get(COLLECTION_PROP_F)
            and collection.get(COLLECTION_PROP_O)
            and collection.get(COLLECTION_PROP_U)
        ):
            lvcp.add_list()
            lvcp.list.name = collection.name.replace("LVCP_", "")
            lvcp.list.collection = collection
            self.report({"INFO"}, "Restored Collection")

    def execute(self, context):
        self._restore_collection(context, self.collection_name)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select Collection to Restore")
        layout.prop(self, "collection", text="Collection")


class LVCP_OT_SelectEmpty(Operator):
    bl_idname = "lvcp.select_empty"
    bl_label = "Select Empty"
    bl_options = {"REGISTER", "UNDO"}

    obj: StringProperty()  # type: ignore

    def execute(self, context):
        select_object(self, context, self.obj)
        return {"FINISHED"}


class LVCP_OT_SelectObject(Operator):
    bl_idname = "lvcp.select_object"
    bl_label = "Select Object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = get_LVCP().list
        objs = get_objects_with_lvcp(self, context, lvcp)
        for obj in objs:
            obj.select_set(True)
        return {"FINISHED"}


class LVCP_OT_ConvertToDriverMode(Operator):
    bl_idname = "lvcp.convert_to_driver_mode"
    bl_label = "Convert To Driver Mode"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = get_LVCP()
        for l in lvcp.lists:
            c = l.collection
            if c:
                oo = c[COLLECTION_PROP_O]
                ff = c[COLLECTION_PROP_F]
                uu = c[COLLECTION_PROP_U]
                if oo:
                    add_custom_prop(oo, OBJECT_PROP_FRONT, [0.0, 0.0, 0.0])
                    add_custom_prop(oo, OBJECT_PROP_UP, [0.0, 0.0, 0.0])
                    set_drivers(target_context=oo, prop_name=OBJECT_PROP_FRONT, expression="var1-var0", obs=[oo, ff], path="location")
                    set_drivers(target_context=oo, prop_name=OBJECT_PROP_UP, expression="var1-var0", obs=[oo, uu], path="location")
                ll = c[COLLECTION_PROP_L]
                if ll:
                    add_custom_prop(ll, OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
                    set_drivers(target_context=ll, prop_name=OBJECT_PROP_LIGHT, expression="var0", obs=[ll], path="matrix_world[2]")
        lvcp.light_vector_nodetree = None
        lvcp.head_vector_nodetree = None
        make_group_node(self, context, True)
        self.report({"INFO"}, "Converted to Driver Mode")
        return {"FINISHED"}


class LVCP_OT_DelNodeTree(Operator):
    bl_idname = "lvcp.del_node_tree"
    bl_label = "Delete Node Tree"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = get_LVCP()
        if lvcp.light_vector_nodetree:
            bpy.data.node_groups.remove(lvcp.light_vector_nodetree)
            lvcp.light_vector_nodetree = None
        if lvcp.head_vector_nodetree:
            bpy.data.node_groups.remove(lvcp.head_vector_nodetree)
            lvcp.head_vector_nodetree = None
        return {"FINISHED"}


class LVCP_List_Main(PropertyGroup):
    name: StringProperty()  # type: ignore
    collection: PointerProperty(type=Collection)  # type: ignore


class LVCP(PropertyGroup):
    lists: CollectionProperty(type=LVCP_List_Main)  # type: ignore
    idx: IntProperty(name="Index", default=0)  # type: ignore
    lvcp_collection: PointerProperty(type=Collection)  # type: ignore
    light_collection: PointerProperty(type=Collection)  # type: ignore
    light_vector_nodetree: PointerProperty(type=NodeTree)  # type: ignore
    head_vector_nodetree: PointerProperty(type=NodeTree)  # type: ignore

    @property
    def list(self):
        try:
            return self.lists[self.idx]
        except IndexError:
            return None

    @property
    def collection(self):
        try:
            return self.list.collection
        except AttributeError:
            return None

    @property
    def name(self):
        try:
            return self.list.name
        except AttributeError:
            return None

    @property
    def light_vector_node(self):
        try:
            return self.light_vector_nodetree
        except AttributeError:
            return None

    @property
    def head_vector_node(self):
        try:
            return self.head_vector_nodetree
        except AttributeError:
            return None

    def add_list(self):
        return self.lists.add()

    def remove_list(self):
        return self.lists.remove(self.idx)


class LVCP_UL_List_Panel(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # layout.prop(item, "collection", text=f"{item.name}", emboss=True, icon="COLLECTION_NEW")
        row = layout.row(align=True)
        row.label(text=f"{item.name}", icon="OUTLINER_COLLECTION")
        row.label(text=f"{len(get_objects_with_lvcp(self,context,item))} items")
        row.operator(LVCP_OT_SelectObject.bl_idname, icon="RESTRICT_SELECT_OFF", text="", emboss=False)
        layout.separator()


class LVCP_PT_Main_Panel(Panel):
    bl_label = "LVCP"
    bl_idname = "LVCP_PT_MainPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LVCP"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        if Lvcp.light_collection is None:
            layout.label(text="Please select Light Collection or Make New One", icon="ERROR")
            layout.prop_search(Lvcp, "light_collection", bpy.data.collections.data, "collections", text="Light Collection")
            layout.operator(LVCP_OT_MakeLightCollection.bl_idname, icon="LIGHT", text="Make Light Collection")
        elif Lvcp.lvcp_collection is None:
            layout.prop_search(Lvcp, "light_collection", bpy.data.collections.data, "collections", text="Light Collection")
            layout.label(text="Please select LVCP Collection or Make New One", icon="ERROR")
            layout.prop_search(Lvcp, "lvcp_collection", bpy.data.collections.data, "collections", text="LVCP Collection")
            layout.operator(LVCP_OT_MakeLVCPCollection.bl_idname, icon="LIGHT", text="Make LVCP Collection")
        else:
            active_lvcp = Lvcp.list
            row1 = layout.row()
            row2 = layout.row()
            row3 = layout.row()
            row = layout.row()
            row.operator(LVCP_OT_AddPropAndEmpty.bl_idname, icon="LIGHT", text="Set Up Light Collection")
            if active_lvcp is None:
                layout.label(text="Please Set Up Light Collection", icon="ERROR")
            else:
                row = layout.row()
                row.operator(LVCP_OT_DelPropAndEmpty.bl_idname, icon="LIGHT", text="Del Prop And Empty")
                row = layout.row()
                row.operator(LVCP_OT_CollectionManager.bl_idname, icon="COLLECTION_NEW", text="Collection Manager")
                row = layout.row()
                row.operator(LVCP_OT_RestoreCollection.bl_idname, icon="COLLECTION_NEW", text="Restore Collection")
                row = layout.row()
                row.operator(LVCP_OT_ConvertToDriverMode.bl_idname, text="Convert To Driver Mode...", icon="DRIVER")
                row = layout.row()
                row.template_list("LVCP_UL_List_Panel", "", Lvcp, "lists", Lvcp, "idx")
                if active_lvcp:
                    layout.prop(active_lvcp, "collection", text="LVCP collection")
                    row = layout.row()
                    row.operator(LVCP_OT_SetPropToObject.bl_idname, icon="OBJECT_DATAMODE", text="Set Prop To Objects")
                    row = layout.row()
                    row.operator(LVCP_OT_DelPropFromObjects.bl_idname, icon="OBJECT_DATAMODE", text="Del Prop From Objects")
                    box = layout.box()
                    box.label(text="Collection Custom Properties")
                    brow = box.row()
                    brow.prop(active_lvcp.collection, f'["{COLLECTION_PROP_F}"]', text=COLLECTION_PROP_F)
                    brow.operator(LVCP_OT_SelectEmpty.bl_idname, icon="RESTRICT_SELECT_OFF", text="").obj = active_lvcp.collection[
                        COLLECTION_PROP_F
                    ].name
                    brow = box.row()
                    brow.prop(active_lvcp.collection, f'["{COLLECTION_PROP_U}"]', text=COLLECTION_PROP_U)
                    brow.operator(LVCP_OT_SelectEmpty.bl_idname, icon="RESTRICT_SELECT_OFF", text="").obj = active_lvcp.collection[
                        COLLECTION_PROP_U
                    ].name
                    brow = box.row()
                    brow.prop(active_lvcp.collection, f'["{COLLECTION_PROP_O}"]', text=COLLECTION_PROP_O)
                    brow.operator(LVCP_OT_SelectEmpty.bl_idname, icon="RESTRICT_SELECT_OFF", text="").obj = active_lvcp.collection[
                        COLLECTION_PROP_O
                    ].name
                    brow = box.row()
                    brow.prop(active_lvcp.collection, f'["{COLLECTION_PROP_L}"]', text=COLLECTION_PROP_L)
                    brow.operator(LVCP_OT_SelectEmpty.bl_idname, icon="RESTRICT_SELECT_OFF", text="").obj = active_lvcp.collection[
                        COLLECTION_PROP_L
                    ].name
                    layout.separator()
                    row = layout.row()
                    row.operator(LVCP_OT_MakeGroupNode.bl_idname, icon="NODE", text="Make Group Node")
                    layout.prop(Lvcp, "light_vector_nodetree", text="Light Vector Node Tree", icon="NODETREE")
                    layout.prop(Lvcp, "head_vector_nodetree", text="Head Vector Node Tree", icon="NODETREE")
                    row = layout.row()
                    row.operator(LVCP_OT_DelNodeTree.bl_idname, icon="NODE", text="Delete Node Tree")


class LVCP_PT_Sub_Prop_Panel(Panel):
    bl_label = "Properties"
    bl_idname = "LVCP_PT_SubPropPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LVCP"
    bl_parent_id = "LVCP_PT_MainPanel"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        lvcp = Lvcp.list
        if lvcp:
            row = layout.row()
            value_column = row.column(align=True)
            value_column.prop(lvcp.collection[COLLECTION_PROP_L], f'["{OBJECT_PROP_LIGHT}"]', text="Matrix Light")
            value_column = row.column(align=True)
            value_column.prop(lvcp.collection[COLLECTION_PROP_O], f'["{OBJECT_PROP_FRONT}"]', text="Matrix Front")
            value_column = row.column(align=True)
            value_column.prop(lvcp.collection[COLLECTION_PROP_O], f'["{OBJECT_PROP_UP}"]', text="Matrix Up")


class LVCP_PT_NodeEditor_Panel(Panel):
    bl_label = "LVCP"
    bl_idname = "LVCP_NodeEditor_Panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "LVCP"

    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row3 = layout.row()
        row1.operator(LVCP_OT_AddGroupNode.bl_idname, icon="NODE", text="Add Group Node")
        row3.template_list("LVCP_UL_List_Panel", "", get_LVCP(), "lists", get_LVCP(), "idx")


classes = [
    LVCP_List_Main,
    LVCP,
    LVCP_OT_AddPropAndEmpty,
    LVCP_OT_MakeGroupNode,
    LVCP_OT_SetPropToObject,
    LVCP_OT_DelPropFromObjects,
    LVCP_OT_AddGroupNode,
    LVCP_OT_DelPropAndEmpty,
    LVCP_OT_MakeLightCollection,
    LVCP_OT_MakeLVCPCollection,
    LVCP_OT_CollectionManager,
    LVCP_OT_RestoreCollection,
    LVCP_OT_SelectEmpty,
    LVCP_OT_SelectObject,
    LVCP_OT_ConvertToDriverMode,
    LVCP_OT_DelNodeTree,
    LVCP_UL_List_Panel,
    LVCP_PT_Main_Panel,
    LVCP_PT_Sub_Prop_Panel,
    LVCP_PT_NodeEditor_Panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.LVCP = bpy.props.PointerProperty(type=LVCP)


def unregister():
    del bpy.types.Scene.LVCP
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
