

import bpy
from bpy.props import StringProperty, BoolProperty, IntProperty, PointerProperty, CollectionProperty
from bpy.types import PropertyGroup, Collection, Object, NodeTree
from . import utils


# region Light Group


class LVCP_LightGroup(PropertyGroup):
    collection: PointerProperty(type=Collection)


# region LVCP List Main


class LVCP_List_Main(PropertyGroup):
    """
    This is the PropertyGroup for a single LVCP instance.
    It uses a state guard ('_is_updating') to safely synchronize the 
    'active_light_index' and 'active_light' properties without infinite loops.
    """
    name: StringProperty()
    collection: PointerProperty(type=Collection, name="LVCP Collection", description="Collection for this LVCP instance.")
    light_master: PointerProperty(type=Object, name="Light Master", description="Empty that holds the final light vector.")
    
    def update_light_group(self, context):
        """Called when the light_group collection is changed."""
        self.light_master = self.light_group.get(utils.Constants.COLLECTION_PROP_MASTER) if self.light_group else None
        if not self.light_master: return

        utils.del_drivers(self.light_master, utils.Constants.OBJECT_PROP_LIGHT)
        objects = self.light_group.objects if self.light_group else []
        if objects:
            utils.set_drivers(
                target_context=self.light_master,
                prop_name=utils.Constants.OBJECT_PROP_LIGHT,
                expression=f'{utils.Constants.DRIVER_FUNCTION}(self["idx"],[{self._make_lights_arg_string()}])',
                obs=objects,
                path1=f'["{utils.Constants.OBJECT_PROP_LIGHT}"]',
                path2="index",
                path3="",
            )
        
        # This will trigger the index update function, which now contains all the necessary logic.
        self.active_light_index = self.active_light_index 

        # Sync collections
        if self.collection.get(utils.Constants.COLLECTION_PROP_L) is None:
            self.collection[utils.Constants.COLLECTION_PROP_L] = self.light_master
        if self.light_group and self.collection.children.get(self.light_group.name) is None:
            for c in self.collection.children:
                if c.name.startswith("LightGroup_"):
                    self.collection.children.unlink(c)
            utils.link_collection(self.collection, self.light_group)

    def update_active_light(self, context):
        """Called when the 'Active Light' dropdown is changed by the user."""
        if self.get("_is_updating"): return
        if not self.active_light or not self.light_group: return

        try:
            idx = self.light_group.objects.find(self.active_light.name)
            if idx != -1:
                self["_is_updating"] = True
                self.active_light_index = idx
                self["_is_updating"] = False
        except (AttributeError, ValueError):
            pass
    
    def update_active_light_index(self, context):
        """Called when the 'Light Index' slider is changed by the user."""
        if self.get("_is_updating"): return
            
        self["_is_updating"] = True

        objects = self.light_group.objects if self.light_group else []
        max_idx = max(0, len(objects) - 1)
        
        clamped_value = max(0, min(self.active_light_index, max_idx))
        
        try:
            # Attempt to update the UI property's soft_max. This makes the slider range visually correct.
            self.id_properties_ui("active_light_index").update(soft_max=max_idx)
        except KeyError:
            # This is safe to ignore if the UI data isn't ready. The clamping below still ensures correctness.
            pass
        
        if self.light_master:
            self.light_master["idx"] = clamped_value
            self.light_master.update_tag()

        if objects and clamped_value < len(objects):
            self.active_light = objects[clamped_value]
            utils.select_object(objects[clamped_value].name)
        
        # IMPORTANT: Write the clamped value back to the property. This must be done inside the guard.
        self.active_light_index = clamped_value

        self["_is_updating"] = False

    # Define the properties that control the active light
    light_group: PointerProperty(type=Collection, update=update_light_group)
    
    active_light: PointerProperty(
        type=Object, 
        name="Active Light", 
        update=update_active_light, 
        description="The currently selected light control empty."
    )
    
    active_light_index: IntProperty(
        name="Light Index",
        description="Index of the active light control empty. Changing this updates the active light and vice-versa.",
        min=0,
        max=3,
        update=update_active_light_index,
    )

    def _make_lights_arg_string(self):
        objects = self.light_group.objects if self.light_group else []
        return ",".join([f"var{i}" for i in range(len(objects))])

    def set_driver_head(self):
        head_origin = self.collection.get(utils.Constants.COLLECTION_PROP_O)

        if not head_origin: return

        utils.del_drivers(head_origin, utils.Constants.OBJECT_PROP_FRONT)
        utils.del_drivers(head_origin, utils.Constants.OBJECT_PROP_UP)
        utils.set_drivers(
            target_context=head_origin, prop_name=utils.Constants.OBJECT_PROP_FRONT,
            expression="-var0", obs=[head_origin], path1="matrix_world", path2="[1]", path3="index"
        )
        utils.set_drivers(
            target_context=head_origin, prop_name=utils.Constants.OBJECT_PROP_UP,
            expression="var0", obs=[head_origin], path1="matrix_world", path2="[2]", path3="index"
        )

    def get_non_light_objects(self):
        objects = self.light_group.objects if self.light_group else []
        return [obj for obj in objects if utils.Constants.OBJECT_PROP_LIGHT not in obj]


# region Main LVCP


class LVCP(PropertyGroup):
    lists: CollectionProperty(type=LVCP_List_Main)
    light_group: CollectionProperty(type=LVCP_LightGroup)
    lvcp_collection: PointerProperty(type=Collection)
    light_collection: PointerProperty(type=Collection)
    idx: IntProperty(name="Index", default=0)
    light_vector_nodetree: PointerProperty(type=NodeTree)
    head_vector_nodetree: PointerProperty(type=NodeTree)
    
    tab: bpy.props.EnumProperty(
        items=[
            ('SETUP', "Setup", "Setup"),
            ('LIGHTING', "Lighting", "Lighting"),
            ('NODES', "Nodes", "Nodes"),
            ('ADVANCED', "Advanced", "Advanced"),
        ],
        default='SETUP'
    )

    @property
    def list(self) -> LVCP_List_Main:
        try:
            return self.lists[self.idx]
        except IndexError:
            return None

    def add_list(self) -> LVCP_List_Main:
        self.idx = len(self.lists)
        return self.lists.add()

    def remove_list(self):
        if len(self.lists) > 0:
            self.lists.remove(self.idx)
            if self.idx >= len(self.lists):
                self.idx = len(self.lists) - 1


# region Registration


classes = (
    LVCP_LightGroup,
    LVCP_List_Main,
    LVCP,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)