# SPDX-License-Identifier: GPL-3.0-or-later

######################################################################################################
# A simple to split an object into different parts                                                   #
# Author: Camptosaurus                                                                               #
# Based on the auto-mirror plugin by Lapineige and Bookyakuno                                        #
# https://github.com/blender/blender-addons/blob/main/mesh_auto_mirror.py                            #
######################################################################################################

bl_info = {
    "name": "Split Parts",
    "description": "Easily cut an object in multiple parts",
    "author": "Camptosaurus",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "View 3D > Sidebar > Edit Tab > SplitParts (panel)",
    "warning": "",
    "category": "Mesh",
}

import os
import re

import bpy
from mathutils import Vector

import bpy
from bpy_extras import view3d_utils
from bpy.types import (
    Panel,
    PropertyGroup,
)

from bpy.props import (
    BoolVectorProperty,
    PointerProperty,
    StringProperty,
    BoolProperty
)

class SplitParts(bpy.types.Operator):
    """ Automatically cut an object along an axis """
    bl_idname = "object.splitparts"
    bl_label = "Split parts"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def get_local_axis_vector(self, object, X, Y, Z):
        current_mode = bpy.context.object.mode

        location = object.location
        bpy.ops.object.mode_set(mode = "OBJECT") # Needed to avoid to translate vertices

        v1 = Vector((location[0], location[1], location[2]))
        bpy.ops.transform.translate(
            value = (X, Y, Z),
            constraint_axis = ((X == 1), (Y == 1), (Z == 1)),
            orient_type = 'LOCAL'
        )

        v2 = Vector((location[0], location[1], location[2]))
        bpy.ops.transform.translate(
            value = (-X, -Y, -Z),
            constraint_axis = ((X == 1), (Y == 1), (Z == 1)),
            orient_type = 'LOCAL'
        )

        bpy.ops.object.mode_set(mode = current_mode)

        return v1 - v2

    def get_inner_and_outer(self, inner):
        bpy.ops.object.mode_set(mode = "OBJECT")

        bpy.ops.object.select_all(action = 'DESELECT')

        inner.select_set(True)
        bpy.context.view_layer.objects.active = inner

        bpy.ops.object.duplicate(linked = False)  
        outer = bpy.context.object

        return inner, outer

    def cut_along_axis(self, objects, X, Y, Z):
        for index, object in enumerate(list(objects)):
            inner, outer = self.get_inner_and_outer(object)

            inner.name = f"Part {index} - {X}-{Y}-{Z} - Inner"
            outer.name = f"Part {index} - {X}-{Y}-{Z} - Outer"

            for subobject, is_inner in [{ inner, True }, { outer, False }]:
                bpy.ops.object.mode_set(mode = "OBJECT")

                bpy.ops.object.select_all(action = 'DESELECT')

                subobject.select_set(True)
                bpy.context.view_layer.objects.active = subobject

                bpy.ops.object.mode_set(mode = "EDIT")

                bpy.ops.mesh.select_all(action = 'SELECT')

                cut_normal = self.get_local_axis_vector(subobject, X, Y, Z)

                # Cut the mesh and keep selected part
                bpy.ops.mesh.bisect(
                    plane_co = (
                        subobject.location[0],
                        subobject.location[1],
                        subobject.location[2]
                    ),
                    plane_no = cut_normal,
                    use_fill = True,
                    clear_inner = not is_inner,
                    clear_outer = is_inner,
                    threshold = 0
                )

                bpy.ops.mesh.normals_make_consistent(inside=False)

    def export_to_stl(self, object, export_path):
        bpy.ops.object.select_all(action = 'DESELECT')
        object.select_set(True)
        bpy.context.view_layer.objects.active = object

        export_path = bpy.path.abspath(export_path)

        # first ensure the path is created
        if export_path:
            # this can fail with strange errors,
            # if the dir can't be made then we get an error later.
            try:
                os.makedirs(export_path, exist_ok=True)
            except:
                import traceback
                traceback.print_exc()

        # Create name 'export_path/blendname-objname'
        # add the filename component
        name = os.path.basename(bpy.data.filepath)
        name = os.path.splitext(name)[0]
        name += "-" + re.sub(r'[\\/:*?"<>|]', "", object.name)

        filepath = os.path.join(export_path, name)

        filepath = bpy.path.ensure_ext(filepath, ".stl")
        bpy.ops.export_mesh.stl(
            filepath=filepath,
            ascii=False,
            use_mesh_modifiers=True,
            use_selection=True,
            global_scale=1.0,
        )

    def execute(self, context):
        splitparts = context.scene.splitparts

        collection_name = f'{context.object.name}_parts'

        # First we create a new collection for our parts
        try:
            collection = bpy.data.collections[collection_name]
        except KeyError:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection)

        # We copy the object in our collection
        bpy.ops.object.duplicate(linked = False)  
        bpy.context.object.name = "part"

        old_collection = context.object.users_collection[0]

        collection.objects.link(context.object)
        old_collection.objects.unlink(context.object)

        # Apply all modifiers
        for modifier in context.object.modifiers:
            bpy.ops.object.modifier_apply(
                modifier=modifier.name
            )

        # Cut and rip
        X, Y, Z = splitparts.axis
        if X:
            self.cut_along_axis(collection.objects, 1, 0, 0)
        if Y:
            self.cut_along_axis(collection.objects, 0, 1, 0)
        if Z:
            self.cut_along_axis(collection.objects, 0, 0, 1)

        bpy.ops.object.mode_set(mode = "OBJECT")

        if splitparts.export:
            for object in collection.objects:
                self.export_to_stl(
                    object = object,
                    export_path = splitparts.export_path
                )

        return {'FINISHED'}

class VIEW3D_PT_BisectParts(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Split Parts"
    bl_category = 'Edit'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        splitparts = context.scene.splitparts

        layout = self.layout

        if bpy.context.object and bpy.context.object.type == 'MESH':
            layout.prop(splitparts, "axis", text = "Axis")
            layout.prop(splitparts, "export", text = "Export to STL")
            if splitparts.export:
                layout.prop(splitparts, "export_path", text = "Path")

            layout.operator("object.splitparts")
        else:
            layout.label(icon="ERROR", text = "No mesh selected")

# Properties
class SplitPartsProps(PropertyGroup):
    axis: BoolVectorProperty(
        default=(False, False, False),
        size=3,
        description="Axis to cut",
        subtype="XYZ"
    )

    export: BoolProperty(
        name="Export to STL",
        description="Export generated parts to STL"
    )

    export_path: StringProperty(
        name="Export Directory",
        description="Path to directory where the files are created",
        default="//",
        maxlen=1024,
        subtype="DIR_PATH",
    )

# define classes for registration
classes = (
    VIEW3D_PT_BisectParts,
    SplitParts,
    SplitPartsProps,
)

# registering and menu integration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.splitparts = PointerProperty(type = SplitPartsProps)

# unregistering and removing menus
def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.splitparts

if __name__ == "__main__":
    register()
