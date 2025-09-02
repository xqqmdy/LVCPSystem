import bpy
import re
from bpy.types import Panel, UIList
from . import utils


# region UI List Class


class LVCP_UL_List_Panel(UIList):
    """The list view for LVCP instances."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="OUTLINER_COLLECTION")
        
        obj_count = len(utils.get_objects_with_lvcp(item))
        row.label(text=f"{obj_count} obj", icon="OBJECT_DATA")
        
        light_group_name = item.light_group.name if item.light_group else "No Group"
        row.label(text=f"{light_group_name}", icon="LIGHT")


# region Panels


class LVCP_PT_Panel_Base:
    """Base class for all LVCP panels in the 3D Viewport."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "LVCP"

class LVCP_PT_Main_Panel(LVCP_PT_Panel_Base, Panel):
    bl_label = "LVCP System"
    bl_idname = "LVCP_PT_MainPanel"

    def draw(self, context):
        layout = self.layout
        lvcp = utils.get_LVCP()

        # Main UI
        row = layout.row()
        row.template_list("LVCP_UL_List_Panel", "", lvcp, "lists", lvcp, "idx")

        col = row.column(align=True)
        col.operator("lvcp.create_instance", icon='ADD', text="")
        col.operator("lvcp.delete_instance", icon='REMOVE', text="")

        col.separator()

        col.operator("lvcp.collection_manager", icon='FILE_REFRESH', text="")
        
        layout.separator()
        
        # Tabs
        row = layout.row(align=True)
        row.prop(lvcp, "tab", expand=True)

        # Draw active tab
        box = layout.box()
        if lvcp.tab == 'SETUP':
            self.draw_setup_tab(box, context)
        elif lvcp.tab == 'LIGHTING':
            self.draw_lighting_tab(box, context)
        elif lvcp.tab == 'NODES':
            self.draw_nodes_tab(box, context)
        elif lvcp.tab == 'ADVANCED':
            self.draw_advanced_tab(box, context)

    def draw_setup_tab(self, layout, context):
        # Auto-detect suitable armature for quick setup
        found_armatures = utils.find_suitable_armatures(context)

        if found_armatures:
            lvcp = utils.get_LVCP()
            for armature in found_armatures:
                # Check if an instance already exists for this armature
                base_name = utils.get_base_name_from_armature(armature.name)
                existing_instance = False
                for item in lvcp.lists:
                    if item.collection and item.collection.name == f"LVCP_{base_name}":
                        existing_instance = True
                        break

                if not existing_instance:
                    op = layout.operator("lvcp.auto_setup_for_armature", text=f"Setup {armature.name}")
                    op.armature_name = armature.name

        row = layout.row(align=True)
        row.operator("lvcp.link_objects", icon="LINKED", text="Link Selected")
        row.operator("lvcp.select_object", icon="RESTRICT_SELECT_OFF", text="Select Linked")

        lvcp_list = utils.get_LVCP().list
        linked_objs = utils.get_objects_with_lvcp(lvcp_list)

        layout.separator()

        if not linked_objs:
            layout.label(text="No objects linked.", icon="INFO")
        else:
            # Show count of linked objects
            layout.label(text=f"{len(linked_objs)} linked object(s)", icon="INFO")
            
            # Display objects in a box for better visual grouping
            obj_box = layout.box()
            for obj in linked_objs:
                row = obj_box.row(align=True)
                row.label(text=obj.name, icon="OBJECT_DATA")
                op = row.operator("lvcp.unlink_objects", icon="X", text="")
                op.obj_name = obj.name

    def draw_lighting_tab(self, layout, context):
        active_lvcp = utils.get_LVCP().list
        
        if not active_lvcp.light_group:
            layout.label(text="No light group assigned.", icon="ERROR")
            return
            
        non_light_obj = active_lvcp.get_non_light_objects()
        if non_light_obj:
            layout.label(text=f"Warning: Non-light objects in group!", icon="ERROR")
            for obj in non_light_obj: layout.label(text=obj.name, icon="OBJECT_DATA")
        
        row = layout.row()
        row.prop_search(active_lvcp, "light_group", utils.get_LVCP().light_collection, "children", text="Group")

        row = layout.row()
        row.prop_search(active_lvcp, "active_light", active_lvcp.light_group, "objects", text="Active")
        
        row = layout.row()
        row.operator("lvcp.add_light_empty", icon="LIGHT", text="Add Light")
        row.prop(active_lvcp, "active_light_index", slider=True, text="Index")

    def draw_nodes_tab(self, layout, context):
        lvcp = utils.get_LVCP()
        layout.prop(lvcp, "light_vector_nodetree", text="")
        layout.prop(lvcp, "head_vector_nodetree", text="")
        row = layout.row(align=True)
        row.operator("lvcp.create_node_groups", icon="NODE", text="Create")
        row.operator("lvcp.delete_node_groups", icon="X", text="Delete")

    def draw_advanced_tab(self, layout, context):
        active_lvcp = utils.get_LVCP().list

        layout.operator("lvcp.restore_driver", icon="DRIVER", text="Restore Drivers")

        box = layout.box()
        box.label(text="Driver Output Vectors")

        light_master = active_lvcp.light_master
        head_origin = active_lvcp.collection.get(utils.Constants.COLLECTION_PROP_O) if active_lvcp.collection else None

        row = box.row(align=True)

        col = row.column()
        if light_master:
            col.prop(light_master, f'["{utils.Constants.OBJECT_PROP_LIGHT}"]', text="Light")
        else:
            col.label(text="Light: N/A", icon="ERROR")

        col = row.column()
        if head_origin:
            col.prop(head_origin, f'["{utils.Constants.OBJECT_PROP_FRONT}"]', text="Forward")
        else:
            col.label(text="Forward: N/A", icon="ERROR")

        col = row.column()
        if head_origin:
            col.prop(head_origin, f'["{utils.Constants.OBJECT_PROP_UP}"]', text="Up")
        else:
            col.label(text="Up: N/A", icon="ERROR")


# region Node Editor Helper


class LVCP_PT_NodeEditor_Panel(Panel):
    bl_label = "LVCP Helper"
    bl_idname = "LVCP_PT_NodeEditor_Panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "LVCP"

    def draw(self, context):
        layout = self.layout
        layout.operator("lvcp.add_node_groups_to_material", icon="NODE", text="Add LVCP Groups")


# region Registration


classes = (
    LVCP_UL_List_Panel,
    LVCP_PT_Main_Panel,
    LVCP_PT_NodeEditor_Panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)