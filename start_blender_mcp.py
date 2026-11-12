import bpy
import addon_utils
addon_utils.enable('blender_mcp', default_set=False)
bpy.ops.blendermcp.start_server()
print('Switch robot design MCP ready')
