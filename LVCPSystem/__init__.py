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

from . import lvcp_system

if "bpy" in locals():
    import sys

    for k, v in list(sys.modules.items()):
        if k.startswith("LVCPSystem."):
            del sys.modules[k]


def register():
    lvcp_system.register_component()


def unregister():
    lvcp_system.unregister_component()


if __name__ == "__main__":
    register()
