# LVCPSystem

## Description
LVCPSystem is a Light Vector and Head Vector Management System for Blender. This add-on provides tools to manage light and head vectors efficiently within Blender.

## Requirements
- Blender 4.0.0 or later

## Installation
1. Download the latest release from the [Releases](https://github.com/Puls-r/LVCPSystem/releases).
2. Open Blender and go to `Edit > Preferences > Add-ons`.
3. Click `Install` and select the downloaded ZIP file.
4. Enable the add-on by checking the box next to `LVCPSystem`.

## Usage
1. Before using LVCP, add a `Light Collection` and `LVCP Collection` to the scene. This can also be done by selecting `LVCP` in the 3D-View side panel and then running `Make Light Collection` and `Make LVCP Collection`.
2. Select an armature or object and execute `Set Up Light Collection`. This will automatically add the necessary collections and empties to the LVCP.
3. Select the object for which you want to use LVCP in the shader.
4. With the objects selected, execute `Set Prop To Objects`.
5. `Make Group Node` is executed to create a group node to reference the LVCP in the shader.
6. Finally, go to the `Shader Editor` and add a group node from the `LVCP` side panel.
> [!TIP]
> `Light_Vector` is **not** `Rotation_Euler` so there is no need to connect it to Vector Rotate.


## Issues
If you find a bug, please provide me with a scene file where you can reproduce the bug so I can quickly debug it.

## License
This project is licensed under the terms of the [LICENSE](../LICENSE) file.

## Contact
Contact me at Discord (pulse.com) if you have any questions/requests/issues.