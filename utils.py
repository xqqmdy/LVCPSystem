# Helper functions and Global constants 

import bpy
import re
from bpy.app.handlers import persistent
from bpy.types import PropertyGroup
from mathutils import Vector
from math import radians


# region Constants


class Constants:
    """Namespace for all addon constants to improve clarity and maintainability."""
    
    # Custom properties for Collections
    COLLECTION_PROP_L = "LL"                 # Pointer to the light master empty
    COLLECTION_PROP_O = "OO"                 # Pointer to the head origin empty
    COLLECTION_PROP_MASTER = "lightMaster"   # Pointer from a LightGroup collection to its master empty

    # Custom properties for Objects
    OBJECT_PROP_COL = "lvcp"                 # Pointer from a mesh to its LVCP collection
    OBJECT_PROP_LIGHT = "vecLight"           # Vector property on light empties and the light master
    OBJECT_PROP_FRONT = "vecFront"           # Vector property on the head origin for forward direction
    OBJECT_PROP_UP = "vecUp"                 # Vector property on the head origin for up direction
    
    # Node Group I/O Names
    NODE_OUTPUT_LIGHT = "Light_Vector"
    NODE_OUTPUT_FORWARD = "Forward_Vector"
    NODE_OUTPUT_UP = "Up_Vector"
    
    # Driver and Naming
    DRIVER_FUNCTION = "lvcp_driver_func"
    HEAD_VECTOR_NODE_NAME = "Head_Vector"


# region Helper Funcs


def find_suitable_armatures(context):
    """Find armatures that match the pattern and have a Head_M bone."""
    armature_pattern = re.compile(r"^(Art|Avatar)_[a-zA-Z]+(?:_\d{2})?$")
    found_armatures = []
    for obj in context.scene.objects:
        if obj.type == 'ARMATURE' and armature_pattern.match(obj.name):
            if 'Head_M' in obj.data.bones:
                found_armatures.append(obj)
    return found_armatures


def get_base_name_from_armature(armature_name):
    """Extract the base name from an armature name."""
    match = re.match(r"^(?:Art|Avatar)_([a-zA-Z]+)(?:_\d{2})?$", armature_name)
    return match.group(1) if match else armature_name


def ensure_initial_collections():
    """Checks if main collections exist and creates them if not. Returns the main LVCP property group."""
    lvcp = get_LVCP()
    collections_created = False
    if lvcp.lvcp_collection is None:
        lvcp_coll = create_collection("LVCP")
        lvcp_coll.color_tag = "COLOR_05"
        lvcp.lvcp_collection = lvcp_coll
        collections_created = True

    if lvcp.light_collection is None:
        light_coll = create_collection("Lights")
        light_coll.color_tag = "COLOR_03"
        lvcp.light_collection = light_coll
        link_collection(lvcp.lvcp_collection, light_coll, True)
        exclude_collection_from_view_layer(light_coll.name)
        collections_created = True
    
    return lvcp, collections_created

def get_LVCP():
    """Convenience function to get the main LVCP property group from the scene."""
    return bpy.context.scene.LVCP

def add_empty(name, size, type, location):
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
        # Avoid unlinking from the master scene collection if it's already there
        if source.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(source)
    # Avoid linking if it already exists
    if source.name not in target.children:
        target.children.link(source)

def exclude_collection_from_view_layer(collection_name):
    target_collection = bpy.data.collections.get(collection_name)
    if not target_collection:
        return

    view_layer = bpy.context.view_layer
    def find_layer_collection(layer_collection, collection):
        if layer_collection.collection == collection:
            return layer_collection
        for child in layer_collection.children:
            found = find_layer_collection(child, collection)
            if found:
                return found
        return None

    layer_collection = find_layer_collection(view_layer.layer_collection, target_collection)
    if layer_collection:
        layer_collection.exclude = True

def get_node_editor_view_center(context):
    for area in context.screen.areas:
        if area.type == "NODE_EDITOR":
            for region in area.regions:
                if region.type == "WINDOW":
                    view2d = region.view2d
                    center_x = (view2d.region_to_view(0, 0)[0] + view2d.region_to_view(region.width, 0)[0]) / 2
                    center_y = (view2d.region_to_view(0, 0)[1] + view2d.region_to_view(0, region.height)[1]) / 2
                    return Vector((center_x, center_y))
    return Vector((0,0)) # Return a default vector if not found

def add_attribute_node(node_tree: bpy.types.NodeTree, name, label, type="OBJECT"):
    attrnode = node_tree.nodes.new(type="ShaderNodeAttribute")
    attrnode.attribute_name = name
    attrnode.label = label
    attrnode.attribute_type = type
    return attrnode

def edit_property(target_context: PropertyGroup, property_name: str):
    return target_context.id_properties_ui(property_name)

def add_custom_prop(target_context, prop_name, obj):
    target_context[prop_name] = obj

def set_drivers(target_context, prop_name, expression, obs, driver_type="SINGLE_PROP", transform_type="LOC", path1="", path2="", path3=""):
    prop_data_path = f'["{prop_name}"]'
    fcurve = target_context.driver_add(prop_data_path)
    if not fcurve: return
    
    drivers_list = fcurve if isinstance(fcurve, list) else [fcurve.driver]
    
    for i, driver in enumerate(drivers_list):
        if not hasattr(driver, 'driver'): continue
        driver.driver.expression = expression
        driver.driver.use_self = True
        
        # Clear existing variables before adding new ones
        for var in list(driver.driver.variables):
            driver.driver.variables.remove(var)

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
    except (TypeError, RuntimeError):
        pass # Ignore errors if driver doesn't exist

def has_lvcp(obj, lvcp_list_item):
    return Constants.OBJECT_PROP_COL in obj and obj[Constants.OBJECT_PROP_COL] == lvcp_list_item.collection

def get_objects_with_lvcp(lvcp_list_item):
    objs = bpy.context.scene.objects
    return [obj for obj in objs if has_lvcp(obj, lvcp_list_item)]

def select_object(obj_name):
    for obj_in_scene in bpy.context.view_layer.objects:
        obj_in_scene.select_set(False)
    target_obj = bpy.data.objects.get(obj_name)
    if target_obj:
        bpy.context.view_layer.objects.active = target_obj
        target_obj.select_set(True)
    
def lvcp_driver_func(idx, values):
    if not values:
        # If the list is empty, return a default Vector.
        return Vector((0.0, 0.0, 1.0))

    if 0 <= idx < len(values):
        return values[idx]
        
    if values and isinstance(values[0], Vector):
        return Vector((0.0, 0.0, 1.0))
    
    return 0.0

@persistent
def load_post_handler(dummy):
    bpy.app.driver_namespace[Constants.DRIVER_FUNCTION] = lvcp_driver_func


# region Registration


def register():
    bpy.app.driver_namespace[Constants.DRIVER_FUNCTION] = lvcp_driver_func

    if load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_post_handler)



def unregister():
    if load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post_handler)

    if Constants.DRIVER_FUNCTION in bpy.app.driver_namespace:
        del bpy.app.driver_namespace[Constants.DRIVER_FUNCTION]