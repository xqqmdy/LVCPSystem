bl_info = {
    "name": "LVCP",
    "description": "Light Vector and Head Vector Management System",
    "author": "Nifs/Pulse",
    "version": (0, 0, 3),
    "blender": (4, 0, 0),
    "location": "View3D",
    "tracker_url": "https://github.com/Puls-r/LVCPSystem/issues",
    "wiki_url": "https://github.com/Puls-r/LVCPSystem",
    "category": "Object",
}

import bpy
from bpy.props import PointerProperty
from bpy.types import Scene

from . import utils
from . import properties
from . import operators
from . import panels

modules = (
    utils,
    properties,
    operators,
    panels,
)

def register():
    for mod in modules:
        mod.register()
    
    # Add the main PropertyGroup to the Scene type
    Scene.LVCP = PointerProperty(type=properties.LVCP)

def unregister():
    # The main scene property is removed automatically when the PropertyGroup is unregistered
    del Scene.LVCP
    
    for mod in reversed(modules):
        mod.unregister()
