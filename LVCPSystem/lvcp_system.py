import bpy
from bpy.app.handlers import persistent
from bpy.types import Operator, Panel, UIList, PropertyGroup, Collection, NodeTree, Scene, Object
from bpy.props import StringProperty, BoolProperty, IntProperty, PointerProperty, CollectionProperty
from mathutils import Vector

##Names##
COLLECTION_PROP_L = "LL"
COLLECTION_PROP_F = "FF"
COLLECTION_PROP_U = "UU"
COLLECTION_PROP_O = "OO"
OBJECT_PROP_COL = "lvcp"
OBJECT_PROP_LIGHT = "vecLight"
OBJECT_PROP_FRONT = "vecFront"
OBJECT_PROP_UP = "vecUp"
NODE_OUTPUT_LIGHT = "Light_Vector"
NODE_OUTPUT_FORWARD = "Forward_Vector"
NODE_OUTPUT_UP = "Up_Vector"
DRIVER_FUNCTION = "lvcp_driver_func"


class LVCP_LightGroup(PropertyGroup):
    collection: PointerProperty(type=Collection)  # type: ignore


class LVCP_List_Main(PropertyGroup):
    name: StringProperty()  # type: ignore
    collection: PointerProperty(type=Collection)  # type: ignore # LVCP_{name}(Collection)
    light_master: PointerProperty(type=Object)  # type: ignore # Master(Empty Object)
    light_group: PointerProperty(type=Collection, update=lambda self, context: self.update_light_group(context))  # type: ignore
    active_light: PointerProperty(type=Object, name="Active Light", update=lambda self, context: self.update_active_light(context))  # type: ignore

    def _make_lights_arg_string(self):
        return ",".join([f"var{i}" for i in range(len(self.light_group.objects))])

    def update_active_light(self, context):
        try:
            new_idx = self.light_group.objects.find(self.active_light.name)
            if self.light_master["idx"] != new_idx:
                self.light_master["idx"] = new_idx
                self.idx = new_idx
        except KeyError:
            self.light_master["idx"] = 0

    def update_light_group(self, context):
        if self.light_master is None:
            return
        del_drivers(self.light_master, OBJECT_PROP_LIGHT)
        set_drivers(
            target_context=self.light_master,
            prop_name=OBJECT_PROP_LIGHT,
            expression=f'{DRIVER_FUNCTION}(self["idx"],[{self._make_lights_arg_string()}])',
            obs=self.light_group.objects,
            path1=f'["{OBJECT_PROP_LIGHT}"]',
            path2="index",
            path3="",
        )
        edit_property(self.light_master, "idx").update(
            min=0, max=len(self.light_group.objects) - 1, soft_min=0, soft_max=len(self.light_group.objects) - 1
        )
        if self.collection.children.get(self.light_group.name) is None:
            for c in self.collection.children:
                if c.name.startswith("LightGroup_"):
                    self.collection.children.unlink(c)

        link_collection(self.collection, self.light_group)

    def set_driver_head(self, context):
        del_drivers(self.light_master, OBJECT_PROP_FRONT)
        del_drivers(self.light_master, OBJECT_PROP_UP)
        set_drivers(
            target_context=self.collection[COLLECTION_PROP_O],
            prop_name=OBJECT_PROP_FRONT,
            expression="-var0",
            obs=[self.collection[COLLECTION_PROP_O]],
            path1="matrix_world",
            path2="[1]",
            path3="index",
        )
        set_drivers(
            target_context=self.collection[COLLECTION_PROP_O],
            prop_name=OBJECT_PROP_UP,
            expression="var0",
            obs=[self.collection[COLLECTION_PROP_O]],
            path1="matrix_world",
            path2="[2]",
            path3="index",
        )

    def hasprop(self, name):
        return hasattr(self.collection, name)


class LVCP(PropertyGroup):
    lists: CollectionProperty(type=LVCP_List_Main)  # type: ignore #TODO: change name
    light_group: CollectionProperty(type=LVCP_LightGroup)  # type: ignore

    lvcp_collection: PointerProperty(type=Collection)  # type: ignore
    light_collection: PointerProperty(type=Collection)  # type: ignore
    idx: IntProperty(name="Index", default=0)  # type: ignore

    light_vector_nodetree: PointerProperty(type=NodeTree)  # type: ignore
    head_vector_nodetree: PointerProperty(type=NodeTree)  # type: ignore

    @property
    def list(self) -> LVCP_List_Main:
        try:
            return self.lists[self.idx]
        except IndexError:
            return None

    def add_list(self) -> LVCP_List_Main:
        return self.lists.add()

    def remove_list(self) -> None:
        return self.lists.remove(self.idx)


def get_LVCP() -> LVCP:
    return bpy.context.scene.LVCP


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


def link_collection(target, source, unlink=False):
    if unlink:
        bpy.context.scene.collection.children.unlink(source)
    target.children.link(source)


def get_node_editor_view_center(context):
    for area in context.screen.areas:
        if area.type == "NODE_EDITOR":
            for region in area.regions:
                if region.type == "WINDOW":
                    view2d = region.view2d
                    center_x = (view2d.region_to_view(0, 0)[0] + view2d.region_to_view(region.width, 0)[0]) / 2
                    center_y = (view2d.region_to_view(0, 0)[1] + view2d.region_to_view(0, region.height)[1]) / 2
                    return Vector((center_x, center_y))
    return None


###node###


def add_attribute_node(node_tree: bpy.types.NodeTree, name, label, type="OBJECT"):
    attrnode = node_tree.nodes.new(type="ShaderNodeAttribute")
    attrnode.attribute_name = name
    attrnode.label = label
    attrnode.attribute_type = type
    return attrnode


def add_l_or_h_group_node(self, context, l, h):
    lvcp = get_LVCP()
    area = context.area
    if area:
        node_tree = area.spaces.active.edit_tree
        if node_tree is None:
            self.report({"ERROR"}, "Not found NodeGroup in area")
            return
        center = get_node_editor_view_center(context)
        if l:
            g = lvcp.light_vector_nodetree
            if g:
                group_node = node_tree.nodes.new(type="ShaderNodeGroup")
                group_node.node_tree = g
                group_node.location = center
                self.report({"INFO"}, "Light Vector Node Group Added")
            else:
                self.report({"ERROR"}, "Not found Light Vector Node Group")
        if h:
            g = lvcp.head_vector_nodetree
            if g:
                group_node = node_tree.nodes.new(type="ShaderNodeGroup")
                group_node.node_tree = lvcp.head_vector_nodetree
                group_node.location = center + Vector((200, 0))
                self.report({"INFO"}, "Head Vector Node Group Added")
            else:
                self.report({"ERROR"}, "Not found Head Vector Node Group")
    else:
        self.report({"ERROR"}, "Not found NodeGroup in area")
        return
    return {"FINISHED"}


###Properties###
def edit_property(target_context: PropertyGroup, property_name: str):
    return target_context.id_properties_ui(property_name)


def add_custom_prop(target_context, prop_name, obj):
    target_context[prop_name] = obj


def set_drivers(target_context, prop_name, expression, obs, driver_type="SINGLE_PROP", transform_type="LOC", path1="", path2="", path3=""):
    prop_data_path = f'["{prop_name}"]'
    fcurve = target_context.driver_add(prop_data_path)
    if isinstance(fcurve, list):
        for i, driver in enumerate(fcurve):
            driver.driver.expression = expression
            driver.driver.use_self = True
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
                    var.targets[0].transform_type = transform_type + ["_X", "_Y", "_Z"][i]
                    var.targets[0].transform_space = "WORLD_SPACE"
    return fcurve


def del_drivers(target_context, prop_name):
    try:
        prop_data_path = f'["{prop_name}"]'
        target_context.driver_remove(prop_data_path)
    except:
        pass


def add_prop_and_empty(self, context, name, set_child_constraints, bone_name, driver_mode):
    coll = create_collection(f"LVCP_{name}")
    target_context = coll

    coll.color_tag = "COLOR_06"

    # create empty objects
    oo = add_empty(self, context, "Head_Origin", 0.5, "PLAIN_AXES", (0, 0, 0))  # Head Origin

    # prepare custom properties
    add_custom_prop(target_context, COLLECTION_PROP_L, None)
    add_custom_prop(target_context, COLLECTION_PROP_O, oo)

    edit_property(target_context, COLLECTION_PROP_L).update(id_type="OBJECT")
    edit_property(target_context, COLLECTION_PROP_O).update(id_type="OBJECT")

    # add objects to collection
    coll.objects.link(oo)

    # parent
    add_custom_prop(oo, OBJECT_PROP_FRONT, [0.0, 0.0, 0.0])
    add_custom_prop(oo, OBJECT_PROP_UP, [0.0, 0.0, 0.0])
    set_drivers(
        target_context=oo, prop_name=OBJECT_PROP_FRONT, expression="-var0", obs=[oo], path1="matrix_world", path2="[1]", path3="index"
    )
    set_drivers(target_context=oo, prop_name=OBJECT_PROP_UP, expression="var0", obs=[oo], path1="matrix_world", path2="[2]", path3="index")
    # create light object
    l_coll = get_LVCP().light_collection
    ll = add_empty(self, context, f"Light_Master_{name}", 0.5, "PLAIN_AXES", (0, 0, 0))
    target_context[COLLECTION_PROP_L] = ll
    # light = bpy.data.lights.new("Sun", "SUN")
    # light_obj = bpy.data.objects.new("Sun", light)
    # light_obj.location = (0, 0, 0)
    # light_obj.rotation_euler = (0, -3.14, 0)
    # l_coll.objects.link(light_obj)
    # light_obj.parent = ll
    add_custom_prop(ll, OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
    # set_drivers(
    #     target_context=ll,
    #     prop_name=OBJECT_PROP_LIGHT,
    #     expression="var0",
    #     obs=[ll],
    #     path1="matrix_world",
    #     path2="[2]",
    #     path3="index",
    # )
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
    link_collection(lvcp.lvcp_collection, coll, True)
    self.report({"INFO"}, "Added Prop and Empty")


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


def lvcp_driver_func(idx, values):
    if 0 <= idx < len(values):
        return values[idx]
    return 0


@persistent
def load_post_handler(dummy):
    bpy.app.driver_namespace[DRIVER_FUNCTION] = lvcp_driver_func


class LVCP_OT_AddPropAndEmpty(Operator):
    bl_idname = "lvcp.add_prop_and_empty_only"
    bl_label = "Add Prop And Empty Only"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(default="")  # type: ignore
    bool_set_child_constants: BoolProperty(name="Set Child Constants", default=True)  # type: ignore
    bone_name: StringProperty(default="")  # type: ignore
    bool_driver_mode: BoolProperty(default=True)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def execute(self, context):
        add_prop_and_empty(self, context, self.name, self.bool_set_child_constants, self.bone_name, self.bool_driver_mode)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        self.name = bpy.context.active_object.name
        layout.prop(self, "name")
        if bpy.context.active_object.type == "ARMATURE":
            layout.label(text="When you set child constants, please select bone.")
            layout.prop(self, "bool_set_child_constants")
            layout.prop_search(self, "bone_name", bpy.context.active_object.data, "bones", text="Bone")
        # layout.prop(self, "bool_driver_mode", text="Driver Mode")


class LVCP_OT_DelPropAndEmpty(Operator):
    bl_idname = "lvcp.del_prop_and_empty_only"
    bl_label = "Del Prop And Empty Only"
    bl_options = {"REGISTER", "UNDO"}

    bool_del_light: BoolProperty(default=False)  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def _del_prop_and_empty(self, context, bool_del_light):
        Lvcp = get_LVCP()
        coll = Lvcp.list.collection
        lgiht = coll[COLLECTION_PROP_L]
        coll[COLLECTION_PROP_L] = None
        objs = coll.objects
        if objs:
            for obj in objs:
                if hasattr(obj, OBJECT_PROP_FRONT) and hasattr(obj, OBJECT_PROP_UP):
                    if bool_del_light:
                        cs = obj.children
                        for c in cs:
                            if c.type == "LIGHT":
                                bpy.data.objects.remove(c)
                    bpy.data.objects.remove(obj)

            bpy.data.collections.remove(coll)
            get_LVCP().remove_list()
            self.report({"INFO"}, "Deleted Prop and Empty")
        else:
            self.report({"ERROR"}, "Not found Prop and Empty")

    def execute(self, context):
        self._del_prop_and_empty(self, context, self.bool_del_light)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        lvcp = get_LVCP().list
        layout = self.layout
        layout.label(text=f"Delete {lvcp.name}?")
        layout.prop(self, "bool_del_light", text="Delete Light")


class LVCP_OT_SetPropToObject(Operator):
    bl_idname = "lvcp.set_prop_to_objects"
    bl_label = "Set Prop To Objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == "OBJECT"

    def _set_prop_to_objcts(self, context):
        objs = bpy.context.selected_objects
        lvcp = get_LVCP().list
        collection = lvcp.collection
        for obj in objs:
            add_custom_prop(obj, OBJECT_PROP_COL, collection)
            edit_property(obj, OBJECT_PROP_COL).update(id_type="COLLECTION")
            obj.data.update()
        self.report({"INFO"}, "Added Prop to Objects")

    def execute(self, context):
        if get_LVCP().list is None:
            self.report({"ERROR"}, "Not found LVCP")
            return
        self._set_prop_to_objcts(context)
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

    def _make_group_node(self, context, driver_mode):
        def make_light_vector_node(driver_mode=False):
            g = bpy.data.node_groups.new(type="ShaderNodeTree", name=NODE_OUTPUT_LIGHT)
            g_out = g.nodes.new("NodeGroupOutput")
            g.interface.new_socket(NODE_OUTPUT_LIGHT, in_out="OUTPUT", socket_type="NodeSocketVector")
            if driver_mode:
                ll = add_attribute_node(
                    g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_L}"]["{OBJECT_PROP_LIGHT}"]', COLLECTION_PROP_L, "OBJECT"
                )
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
            ff = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_O}"]["{OBJECT_PROP_FRONT}"]', COLLECTION_PROP_F, "OBJECT")
            uu = add_attribute_node(g, f'["{OBJECT_PROP_COL}"]["{COLLECTION_PROP_O}"]["{OBJECT_PROP_UP}"]', COLLECTION_PROP_U, "OBJECT")
            g.links.new(g_out.inputs[NODE_OUTPUT_FORWARD], ff.outputs["Vector"])
            g.links.new(g_out.inputs[NODE_OUTPUT_UP], uu.outputs["Vector"])
            return g

        lvcp = get_LVCP()
        if lvcp.head_vector_nodetree and lvcp.light_vector_nodetree:
            self.report({"ERROR"}, "Already added Node Group")
        if lvcp.head_vector_nodetree is None:
            lvcp.head_vector_nodetree = make_head_vector_node(driver_mode)
        if lvcp.light_vector_nodetree is None:
            lvcp.light_vector_nodetree = make_light_vector_node(driver_mode)
        return {"FINISHED"}

    def execute(self, context):
        self._make_group_node(context, self.driver_mode)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout


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
        coll.color_tag = "COLOR_03"
        get_LVCP().light_collection = coll
        link_collection(get_LVCP().lvcp_collection, coll, True)
        return {"FINISHED"}


class LVCP_OT_MakeLVCPCollection(Operator):
    bl_idname = "lvcp.make_lvcp_collection"
    bl_label = "Make LVCP Collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        coll = create_collection("LVCP")
        coll.color_tag = "COLOR_05"
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
                link_collection(lvcp.lvcp_collection, c, unlink)
        c = lvcp.light_collection
        if c.name not in [child.name for child in lvcp.lvcp_collection.children]:
            link_collection(lvcp.lvcp_collection, c, unlink)
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
    bl_description = "Restore from collections with OO and LL properties"

    collection_name: StringProperty(name="Collection")  # type: ignore

    def _restore_collection(self, context, collection_name):
        lvcp = get_LVCP()
        collection = bpy.data.collections.get(collection_name)
        if collection is None:
            self.report({"ERROR"}, "Not found Collection")
        if collection.get(COLLECTION_PROP_L) and collection.get(COLLECTION_PROP_O):
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


class LVCP_OT_ReplaceNode(Operator):
    bl_idname = "lvcp.replace_node"
    bl_label = "Replace Node"
    bl_options = {"REGISTER", "UNDO"}

    replace_to: StringProperty()  # type: ignore

    @classmethod
    def poll(cls, context):
        return context.area.type == "NODE_EDITOR" and context.active_node

    def execute(self, context):
        lvcp = get_LVCP()
        node_tree = None
        if self.replace_to == "Light Vector":
            node_tree = lvcp.light_vector_nodetree
        elif self.replace_to == "Head Vector":
            node_tree = lvcp.head_vector_nodetree
        active_node = context.active_node
        if active_node and active_node.type == "GROUP":
            active_node.node_tree = node_tree
            self.report({"INFO"}, f"Replaced {self.replace_to}")
        else:
            self.report({"ERROR"}, "Not found Group Node")
        return {"FINISHED"}


class LVCP_OT_AddLightGroup(Operator):
    bl_idname = "lvcp.add_light_group"
    bl_label = "Add Light Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        Lvcp = get_LVCP()
        idx = len(Lvcp.light_group)
        coll = create_collection("LightGroup_" + str(idx))
        link_collection(Lvcp.light_collection, coll, True)
        Lvcp.light_group.add()
        Lvcp.light_group[idx].collection = coll
        lvcp = Lvcp.list
        link_collection(lvcp.collection, coll)
        lvcp.light_group = coll
        if lvcp.collection[COLLECTION_PROP_L]:
            lvcp.light_master = lvcp.collection[COLLECTION_PROP_L]
            add_custom_prop(lvcp.light_master, "idx", 0)
            edit_property(lvcp.light_master, "idx").update(min=0)
            lvcp.collection.objects.link(lvcp.light_master)
        self.report({"INFO"}, "Added Light Group")
        lvcp.update_light_group(context)
        return {"FINISHED"}


class LVCP_OT_RestoreDriver(Operator):
    bl_idname = "lvcp.restore_driver"
    bl_label = "Restore Driver"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lvcp = get_LVCP()
        if lvcp.list:
            lvcp.list.update_light_group(context)
            lvcp.list.set_driver_head(context)
        return {"FINISHED"}


class LVCP_OT_AddLightEmpty(Operator):
    bl_idname = "lvcp.add_light_empty"
    bl_label = "Add Light Empty"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        Lvcp = get_LVCP()
        lv_lcol = Lvcp.light_collection
        lvcp = Lvcp.list
        empty = add_empty(self, context, f"Light_Direction_{lvcp.idx}", 0.5, "SINGLE_ARROW", (0, 0, 0))
        add_custom_prop(empty, OBJECT_PROP_LIGHT, [0.0, 0.0, 0.0])
        set_drivers(
            target_context=empty,
            prop_name=OBJECT_PROP_LIGHT,
            expression="var0",
            obs=[empty],
            path1="matrix_world",
            path2="[2]",
            path3="index",
        )
        lv_lcol.objects.link(empty)
        lvcp.light_group.objects.link(empty)
        lvcp.update_light_group(context)
        if lvcp.active_light is None:
            lvcp.active_light = empty
        self.report({"INFO"}, "Added Light Empty")
        return {"FINISHED"}


class LVCP_UL_List_Panel(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=f"{item.name}", icon="OUTLINER_COLLECTION")
        row.label(text=f"{len(get_objects_with_lvcp(self,context,item))} items")
        row.operator(LVCP_OT_SelectObject.bl_idname, icon="RESTRICT_SELECT_OFF", text="", emboss=False)
        layout.separator()


class LVCP_PT_Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LVCP"

    @classmethod
    def poll(cls, context):
        return get_LVCP().list is not None


class LVCP_PT_Main_Panel(Panel):
    bl_label = "LVCP"
    bl_idname = "LVCP_PT_MainPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LVCP"
    bl_parent_id = "NT_PT_MainPanel" if "NIFSTools" in bpy.context.preferences.addons else ""
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        if Lvcp.lvcp_collection is None:
            layout.label(text="Please select LVCP Collection or Make New One", icon="ERROR")
            layout.prop_search(Lvcp, "lvcp_collection", bpy.data.collections.data, "collections", text="LVCP Collection")
            layout.operator(LVCP_OT_MakeLVCPCollection.bl_idname, icon="LIGHT", text="Make LVCP Collection")
        elif Lvcp.light_collection is None:
            layout.prop_search(Lvcp, "lvcp_collection", bpy.data.collections.data, "collections", text="LVCP Collection")
            layout.label(text="Please select Light Collection or Make New One", icon="ERROR")
            layout.prop_search(Lvcp, "light_collection", bpy.data.collections.data, "collections", text="Light Collection")
            layout.operator(LVCP_OT_MakeLightCollection.bl_idname, icon="LIGHT", text="Make Light Collection")
        else:
            active_lvcp = Lvcp.list
            row = layout.row()
            row.operator(LVCP_OT_AddPropAndEmpty.bl_idname, icon="LIGHT", text="Set Up Light Collection")
            if active_lvcp is None:
                layout.label(text="Please Set Up Light Collection", icon="ERROR")
            else:
                row = layout.row()
                row.operator(LVCP_OT_DelPropAndEmpty.bl_idname, icon="X", text="Del Prop And Empty")
                row = layout.row()
                row.operator(LVCP_OT_CollectionManager.bl_idname, icon="COLLECTION_NEW", text="Collection Manager")
                row = layout.row()
                row.operator(LVCP_OT_RestoreCollection.bl_idname, icon="COLLECTION_NEW", text="Restore Collection")
                row = layout.row()
                row.template_list("LVCP_UL_List_Panel", "", Lvcp, "lists", Lvcp, "idx")
                if active_lvcp:
                    layout.prop(active_lvcp, "collection", text="LVCP collection")
                    row = layout.row()
                    row.operator(LVCP_OT_SetPropToObject.bl_idname, icon="OBJECT_DATAMODE", text="Set Prop To Objects")
                    row.operator(LVCP_OT_DelPropFromObjects.bl_idname, icon="X", text="Del Prop From Objects")


class LVCP_PT_Sub_Collection_Property_Panel(LVCP_PT_Panel, Panel):
    bl_label = "Collection Property"
    bl_idname = "LVCP_PT_SubCollectionPropertyPanel"
    bl_parent_id = "LVCP_PT_MainPanel"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        active_lvcp = Lvcp.list
        if active_lvcp:
            box = layout.box()
            box.label(text="Collection Custom Properties")
            row = box.row()
            row.prop(active_lvcp.collection, f'["{COLLECTION_PROP_O}"]', text=COLLECTION_PROP_O)
            row.operator(LVCP_OT_SelectEmpty.bl_idname, icon="RESTRICT_SELECT_OFF", text="").obj = active_lvcp.collection[
                COLLECTION_PROP_O
            ].name
            row = box.row()
            row.prop(active_lvcp.collection, f'["{COLLECTION_PROP_L}"]', text=COLLECTION_PROP_L)
            row.operator(LVCP_OT_SelectEmpty.bl_idname, icon="RESTRICT_SELECT_OFF", text="").obj = active_lvcp.collection[
                COLLECTION_PROP_L
            ].name
            layout.separator()


class LVCP_PT_Sub_LightGroup_Panel(LVCP_PT_Panel, Panel):
    bl_label = "Light Group"
    bl_idname = "LVCP_PT_SubLightGroupPanel"
    bl_parent_id = "LVCP_PT_MainPanel"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        active_lvcp = Lvcp.list
        if active_lvcp.light_group:
            box = layout.box()
            row = box.row()
            row.prop(active_lvcp, "light_master", text="Light Master")
            row = box.row()
            row.prop(active_lvcp, "light_group", text="Light Group")
            row = box.row()
            row.prop(active_lvcp.light_master, f'["idx"]', text="Index")
            row.prop_search(active_lvcp, "active_light", active_lvcp.light_group, "objects", text="Active Light")
            row = box.row()
            row.operator(LVCP_OT_AddLightEmpty.bl_idname, icon="LIGHT", text="Add Light Empty")
        else:
            layout.label(text="Please Add Light Group or Select Light Group", icon="ERROR")
            layout.operator(LVCP_OT_AddLightGroup.bl_idname, icon="LIGHT", text="Add Light Group")
            layout.prop_search(active_lvcp, "light_group", Lvcp, "light_group", text="Light Group")


class LVCP_PT_Sub_NodeTree_Panel(LVCP_PT_Panel, Panel):
    bl_label = "Node Tree"
    bl_idname = "LVCP_PT_SubNodeTreePanel"
    bl_parent_id = "LVCP_PT_MainPanel"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        box = layout.box()
        row = box.row(align=True)
        row.prop(Lvcp, "light_vector_nodetree", text="Light Vector Node Tree", icon="NODETREE")
        row = box.row(align=True)
        row.prop(Lvcp, "head_vector_nodetree", text="Head Vector Node Tree", icon="NODETREE")
        row = box.row()
        row.operator(LVCP_OT_MakeGroupNode.bl_idname, icon="NODE", text="Make Group Node")
        row.operator(LVCP_OT_DelNodeTree.bl_idname, icon="NODE", text="Delete Node Tree")


class LVCP_PT_Sub_Prop_Panel(LVCP_PT_Panel, Panel):
    bl_label = "Properties"
    bl_idname = "LVCP_PT_SubPropPanel"
    bl_parent_id = "LVCP_PT_MainPanel"
    bl_order = 3

    def draw(self, context):
        layout = self.layout
        Lvcp = get_LVCP()
        lvcp = Lvcp.list
        if lvcp:
            box = layout.box()
            row = box.row()
            value_column = row.column(align=True)

            value_column.prop(lvcp.collection[COLLECTION_PROP_L], f'["{OBJECT_PROP_LIGHT}"]', text=OBJECT_PROP_LIGHT)

            value_column = row.column(align=True)

            value_column.prop(lvcp.collection[COLLECTION_PROP_O], f'["{OBJECT_PROP_FRONT}"]', text=OBJECT_PROP_FRONT)

            value_column = row.column(align=True)
            value_column.prop(lvcp.collection[COLLECTION_PROP_O], f'["{OBJECT_PROP_UP}"]', text=OBJECT_PROP_UP)


class LVCP_PT_NodeEditor_Panel(LVCP_PT_Panel, Panel):
    bl_label = "LVCP"
    bl_idname = "LVCP_PT_NodeEditor_Panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "LVCP"

    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row3 = layout.row()
        row1.operator(LVCP_OT_AddGroupNode.bl_idname, icon="NODE", text="Add Group Node")
        row3.template_list("LVCP_UL_List_Panel", "", get_LVCP(), "lists", get_LVCP(), "idx")
        row = layout.row()
        row.operator(LVCP_OT_ReplaceNode.bl_idname, text="Replace to Light Vector", icon="NODE").replace_to = "Light Vector"
        row.operator(LVCP_OT_ReplaceNode.bl_idname, text="Replace to Head Vector", icon="NODE").replace_to = "Head Vector"


classes = [
    LVCP_LightGroup,
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
    LVCP_OT_DelNodeTree,
    LVCP_OT_ReplaceNode,
    LVCP_OT_AddLightGroup,
    LVCP_OT_RestoreDriver,
    LVCP_OT_AddLightEmpty,
    LVCP_UL_List_Panel,
    LVCP_PT_Main_Panel,
    LVCP_PT_Sub_Collection_Property_Panel,
    LVCP_PT_Sub_LightGroup_Panel,
    LVCP_PT_Sub_Prop_Panel,
    LVCP_PT_Sub_NodeTree_Panel,
    LVCP_PT_NodeEditor_Panel,
]


def register_component():
    for cls in classes:
        bpy.utils.register_class(cls)
    Scene.LVCP = PointerProperty(type=LVCP)
    bpy.app.driver_namespace[DRIVER_FUNCTION] = lvcp_driver_func
    bpy.app.handlers.load_post.append(load_post_handler)


def unregister_component():
    bpy.app.handlers.load_post.remove(load_post_handler)
    if bpy.app.driver_namespace[DRIVER_FUNCTION]:
        del bpy.app.driver_namespace[DRIVER_FUNCTION]
    del Scene.LVCP
    for cls in classes:
        bpy.utils.unregister_class(cls)
