bl_info = {
    "name": "ConverterPIX Wrapper for conversion & import of SCS Game Models",
    "description": "Wrapper add-on to use ConvPIX within the Blender and import SCS game models with ease.",
    "author": "Simon Lusenc (50keda)",
    "version": (2, 1),
    "blender": (2, 81, 0),
    "location": "File > Import > SCS Models - ConverterPIX & BT (*.scs)",
    "category": "Import-Export",
    "support": "COMMUNITY"
}

import bpy
import os
import subprocess
import shutil
from sys import platform
from tempfile import mkdtemp
from threading import Thread
from time import time
from bpy.props import StringProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty, FloatProperty
from bpy.types import AddonPreferences
from bpy_extras.io_utils import ImportHelper

# use blender configuration directories to save converter pix binary,
# this way we can avoid permission problems of saving exe file
CONVERTER_PIX_DIR = os.path.join(bpy.utils.resource_path('USER'), "config/ConverterPIXWrapper")

if not os.path.isdir(CONVERTER_PIX_DIR):
    os.makedirs(CONVERTER_PIX_DIR, exist_ok=True)

if platform == "linux":
    CONVERTER_PIX_URL = "https://github.com/simon50keda/ConverterPIX/raw/master/bin/linux/converter_pix"
    CONVERTER_PIX_PATH = os.path.join(CONVERTER_PIX_DIR, "converter_pix")
    LINE_SPLITTER = "\n"
elif platform == "darwin":
    CONVERTER_PIX_URL = "https://github.com/theHarven/ConverterPIX/raw/MacOS_binary/bin/macos/converter_pix"
    CONVERTER_PIX_PATH = os.path.join(CONVERTER_PIX_DIR, "converter_pix")
    LINE_SPLITTER = "\n"
else:
    CONVERTER_PIX_URL = "https://github.com/mwl4/ConverterPIX/raw/master/bin/win_x86/converter_pix.exe"
    CONVERTER_PIX_PATH = os.path.join(CONVERTER_PIX_DIR, "converter_pix.exe")
    LINE_SPLITTER = "\r\n"


def path_join(path1, path2):
    """Joins path1 with path2 and replaces backslashes with forward ones.
    Needed for proper navigation inside archive tree on Windows.
    """
    return os.path.join(path1, path2).replace("\\", "/")


def update_converter_pix():
    """Downloads ConverterPIX from github and saves it to CONVERTER_PIX_PATH.
    :returns: True if successfully updated; False otherwise
    :rtype: bool
    """

    print("Downloading ConverterPIX...")

    try:
        from urllib3 import disable_warnings
        from requests import get

        # disable urllib warnings so we don't get complains over unauthorized converter pix download
        disable_warnings()

        # create unauthorized get request and download converter pix
        result = get(CONVERTER_PIX_URL, verify=False)
        with open(CONVERTER_PIX_PATH, "wb") as f:
            f.write(result.content)

        # make it executable on linux
        if platform == "linux" or platform == "darwin":

            from stat import S_IEXEC, S_IXGRP

            st = os.stat(CONVERTER_PIX_PATH)
            os.chmod(CONVERTER_PIX_PATH, st.st_mode | S_IEXEC | S_IXGRP)

    except Exception as e:

        from traceback import format_exc

        trace_str = format_exc().replace("\n", "\n\t")
        print("Unexpected %s error accured duing updating of ConverterPIX:\n\t%s\n" % (type(e).__name__, trace_str))
        return False

    print("ConverterPix updated!")
    return True


def run_converter_pix(args):
    """Runs ConverterPIX via CLI.
    1. On linux run it trough wine
    2. Mac OS X currently not supported

    In case return code is different from 0, sth went wrong.

    :param args: Arguments for converter pix
    :type args: list[str]
    :return: return code and stdout from converter pix devided into lines; empty list on error or not supported OS
    :rtype:  tuple[int, list[str]]
    """

    final_command = [CONVERTER_PIX_PATH]
    final_command.extend(args)

    print(final_command)

    result = subprocess.run(final_command, stdout=subprocess.PIPE)

    # if there was some problem running converter pix just return empty list
    if result.returncode != 0:
        return result.returncode, []

    # also return non-zero code if converter pix alone is reporting errors in output
    if "<error>".encode("utf-8") in result.stdout:
        return -1, result.stdout.decode("utf-8").split(LINE_SPLITTER)

    decoded_result = result.stdout.decode("utf-8").split(LINE_SPLITTER)

    for line in decoded_result:
        print(line)

    return result.returncode, decoded_result


def get_archive_listdir(file_paths, current_subpath):
    """Get archive directory listing for given subpath.

    :param file_paths: list of paths that should be used as base archives for converter pix
    :type file_paths: list[str]
    :param current_subpath: current subpath inside of archives
    :type current_subpath: str
    :return: returns two lists: directories and files
    :rtype: (list[str], list[str])
    """

    args = []

    for file_path in file_paths:
        args.extend(["-b", file_path])

    args.extend(["-listdir", current_subpath])
    retcode, stdout = run_converter_pix(args)

    dirs = []
    files = []

    if retcode != 0:
        print("Error getting archive directory listing output from ConverterPIX!")

    for line in stdout:
        if line.startswith("[D] "):
            dirs.append(os.path.relpath(line[4:], current_subpath))
        elif line.startswith("[F] "):
            files.append(os.path.relpath(line[4:], current_subpath))

    return sorted(dirs), sorted(files)


# ### PROPERTIES ###


class ConvPIXWrapperAddonPrefs(AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("world.converter_pix_wrapper_update_exe", icon="URL")


class ConvPIXWrapperFileEntry(bpy.types.PropertyGroup):
    """Property group holding browser file entry data."""

    do_import: BoolProperty(description="Proccess this entry for conversion/import.")
    name: StringProperty(description="Name of the entry represeting name of the file or directory.")
    is_dir: BoolProperty(description="Taging this entry as directory.")


class ConvPIXWrapperBrowserData(bpy.types.PropertyGroup):
    """Property group representing file browser data."""

    def is_subpath_valid(self):
        """Checks if current set subpath is valid for currently set archives.

        :return: True if any dirs and files is returned; False otherwise
        :rtype: bool
        """

        archive_paths = [archive_path.name for archive_path in self.archive_paths]
        dirs, files = get_archive_listdir(archive_paths, self.current_subpath)
        if len(dirs) > 0 or len(files) > 0:
            return True

        return False

    def update_active_entry(self, context):
        """Update function for navigation trough tree of archive:
        1. When directory is selected it advances to it and refreshes the list.
        2. When parent directory '..' is selected it returns one level up and refreshes the list.
        3. When file is selected nothing happens.
        """

        # update current subpath only if proper active entry selected
        if 0 <= self.active_entry < len(self.file_entries):

            active_file_entry = self.file_entries[self.active_entry]

            print("New active item:", active_file_entry.name)

            # only advance in tree if active entry is directory
            if active_file_entry.is_dir:

                if active_file_entry.name == "..":
                    if self.current_subpath != "/":
                        self.current_subpath = os.path.dirname(self.current_subpath)
                else:
                    self.current_subpath = path_join(self.current_subpath, active_file_entry.name)

                self.active_entry = -1

                # abort execution here, as setting active entry to -1 will anyway trigger another update
                return

            elif active_file_entry.name != "..":  # file was selected just return and do nothing with selection
                return

        # remove old entries
        while len(self.file_entries) > 0:
            self.file_entries.remove(0)

        # add entry for navigating to parent directory
        entry = self.file_entries.add()
        entry.name = ".."
        entry.is_dir = True

        # add actual entries from archives
        archive_paths = [archive_path.name for archive_path in self.archive_paths]
        dirs, files = get_archive_listdir(archive_paths, self.current_subpath)
        for dir_name in dirs:
            entry = self.file_entries.add()
            entry.name = dir_name
            entry.is_dir = True

        for file_name in files:

            # ignore file that don't match prescribed extension, if asteriks then everything should be displayed
            if not file_name.endswith(self.file_extension) and self.file_extension != "*":
                continue

            entry = self.file_entries.add()
            entry.name = file_name
            entry.is_dir = False

    multi_select: BoolProperty(
        description="Can multiple files be selected?"
    )

    file_extension: StringProperty(
        description="File extension for the files that should be listed in this browser data.",
        default="*",
    )

    archive_paths: CollectionProperty(
        description="Paths to archives from which directories and files should be listed.",
        type=bpy.types.OperatorFileListElement,
    )

    current_subpath: StringProperty(
        description="Current position in archive tree.",
        default="/",
    )

    file_entries: CollectionProperty(
        description="Collection of file entries for current position in archive tree.",
        type=ConvPIXWrapperFileEntry,
    )

    active_entry: IntProperty(
        description="Currently selected directory/file in browser.",
        default=-1,
        update=update_active_entry
    )


class ConvPIXWrapperArchiveToUse(bpy.types.PropertyGroup):
    """Property group holding entry data for archives to use."""

    path: StringProperty(description="Path to archive.")
    selected: BoolProperty(description="Marking this path as selected. Once selected it can be deleted or moved in the list.")


# ### OPERATORS ###


class CONV_PIX_WRAPPER_UL_FileEntryItem(bpy.types.UIList):
    """Class for drawing archive browser file entry."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):

        if item.name == "..":
            icon = "FILE_PARENT"
        elif item.is_dir:
            icon = "FILE_FOLDER"
        else:
            icon = "FILE_BLANK"

        split_line = layout.split(factor=0.8)
        split_line.prop(item, "name", text="", emboss=False, icon=icon)

        if data.multi_select and not item.is_dir:

            row = split_line.row()
            row.alignment = "RIGHT"
            row.prop(item, "do_import", text="")


class CONV_PIX_WRAPPER_OT_ListImport(bpy.types.Operator):
    bl_idname = "converter_pix_wrapper.list_and_import"
    bl_label = "Converter PIX Wrapper"
    bl_options = {'UNDO', 'INTERNAL'}

    __static_last_model_subpath = "/"
    __static_last_anim_subpath = "/"
    __static_browsers_slider = 0.5

    archive_paths: CollectionProperty(
        description="Paths to archives from which directories and files should be listed.",
        type=bpy.types.OperatorFileListElement,
    )

    only_convert: BoolProperty(
        description="Use ConverterPIX only for conversion of resources into SCS Project Base Path and import manually later?",
    )

    textures_to_base: BoolProperty(
        description="Should textures be copied into the sibling 'base' directory, so they won't be included in mod packing?",
    )

    import_animations: BoolProperty(
        name="Use Animations",
        description="Select animations for conversion and import?\n"
                    "Gives you ability to convert and import animations for selected model (use it only if you are working with animated model)."
    )

    model_browser_data: PointerProperty(
        description="Archive browser data for model selection.",
        type=ConvPIXWrapperBrowserData
    )

    anim_browser_data: PointerProperty(
        description="Archive browser data for animations selection.",
        type=ConvPIXWrapperBrowserData
    )

    browsers_slider: FloatProperty(
        name="Browsers Slider",
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        default=0.5
    )

    def check(self, context):
        return True  # always trigger redraw to avoid problems of popup dialog UIList not drawing properly

    def invoke(self, context, event):

        # prepare browsers data and forcly trigger update, to load up root archive entries

        for archive_path in self.archive_paths:
            entry = self.model_browser_data.archive_paths.add()
            entry.name = archive_path.name
            entry = self.anim_browser_data.archive_paths.add()
            entry.name = archive_path.name

        self.model_browser_data.current_subpath = CONV_PIX_WRAPPER_OT_ListImport.__static_last_model_subpath
        if not self.model_browser_data.is_subpath_valid():
            self.model_browser_data.current_subpath = "/"

        self.anim_browser_data.current_subpath = CONV_PIX_WRAPPER_OT_ListImport.__static_last_anim_subpath
        if not self.anim_browser_data.is_subpath_valid():
            self.anim_browser_data.current_subpath = "/"

        self.model_browser_data.file_extension = ".pmg"
        self.anim_browser_data.file_extension = ".pma"

        self.anim_browser_data.multi_select = True

        self.model_browser_data.update_active_entry(context)
        self.anim_browser_data.update_active_entry(context)

        self.browsers_slider = CONV_PIX_WRAPPER_OT_ListImport.__static_browsers_slider

        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):

        from io_scs_tools.utils import get_scs_globals

        self.save_current_operator_settings()

        if self.model_browser_data.active_entry == -1:
            self.report({'WARNING'}, "No active model selected, aborting import!")
            return {'CANCELLED'}

        model_file_entry_name = self.model_browser_data.file_entries[self.model_browser_data.active_entry].name
        model_archive_subpath = path_join(self.model_browser_data.current_subpath, model_file_entry_name)

        # collect all selected animations from animations browser
        anim_archive_subpaths = []
        if self.import_animations:

            for anim_file_entry in self.anim_browser_data.file_entries:
                if anim_file_entry.do_import:
                    anim_archive_subpaths.append(path_join(self.anim_browser_data.current_subpath, anim_file_entry.name[:-4]))

        # temporarly convert to temp directory to be able to extract textures and models separately
        export_path = mkdtemp()

        # put together arguments for converter pix
        args = []

        for archive_path in self.archive_paths:
            args.extend(["-b", archive_path.name])

        args.extend(["-m", model_archive_subpath[:-4]])
        args.extend(anim_archive_subpaths)
        args.extend(["-e", export_path])

        # execute conversion
        retcode, stdout = run_converter_pix(args)

        if retcode != 0:
            msg = "ConverterPIX crashed or encountered error! Standard output returned:"
            print(msg)
            self.report({'ERROR'}, msg)

            for line in stdout:
                if line != "":
                    print(line)
                    self.report({'ERROR'}, line)

            return {'CANCELLED'}

        # calculate models & textures project path
        models_project_path = textures_project_path = get_scs_globals().scs_project_path
        if self.textures_to_base:
            textures_project_path = os.path.join(models_project_path, os.pardir, "base")

        # distribute converted data to appropriate folder
        for root, dirs, files in os.walk(export_path, topdown=False):
            file_subdir = os.path.relpath(root, export_path)
            for file in files:
                if file.endswith(".tobj") or file.endswith(".dds") or file.endswith(".png"):
                    file_dstdir = os.path.join(textures_project_path, file_subdir)
                else:
                    file_dstdir = os.path.join(models_project_path, file_subdir)

                os.makedirs(file_dstdir, exist_ok=True)

                src_path = os.path.join(root, file)
                dst_path = os.path.join(file_dstdir, file)
                shutil.move(src_path, dst_path)

            # dirs cleanup - with the help of disabled topdown listing, remove empty dirs here including topmost export path
            os.rmdir(root)

        # now do actual import with BT
        if not self.only_convert:

            pim_import_file = model_file_entry_name[:-4] + ".pim"
            pim_import_dir = os.path.abspath(path_join(get_scs_globals().scs_project_path, self.model_browser_data.current_subpath[1:]))

            bpy.ops.scs_tools.import_pim(files=[{"name": pim_import_file}], directory=pim_import_dir)

        return {'FINISHED'}

    def save_current_operator_settings(self):
        # backup last sub-paths to return to them eventually
        CONV_PIX_WRAPPER_OT_ListImport.__static_last_model_subpath = self.model_browser_data.current_subpath
        CONV_PIX_WRAPPER_OT_ListImport.__static_last_anim_subpath = self.anim_browser_data.current_subpath

        # backup ui browsers divider value
        CONV_PIX_WRAPPER_OT_ListImport.__static_browsers_slider = self.browsers_slider

        print("Saving current settings for ConverterPIXWrapper import operator...")

    def cancel(self, context):
        self.save_current_operator_settings()

    def draw(self, context):
        layout = self.layout

        # clip browsers slider to proper upper and lower values to avoid UI problems with split
        if self.browsers_slider < 0.1 or self.browsers_slider > 0.85:
            self.browsers_slider = min(0.85, max(0.1, self.browsers_slider))

        archive_names = [os.path.basename(archive_path.name) for archive_path in self.archive_paths]
        layout.label(text="Currently working upon: %r." % archive_names)

        # browsers slider ratio
        layout.prop(self, "browsers_slider")

        browser_layout = layout.split(factor=self.browsers_slider)

        left_column = browser_layout.column(align=True)
        right_column = browser_layout.column(align=True)

        usage_type = "convert" if self.only_convert else "convert & import"

        # left browser
        left_column.label(text="Model to %s:" % usage_type)
        subpath_row = left_column.row(align=True)
        subpath_row.enabled = False
        subpath_row.prop(self.model_browser_data, "current_subpath", text="")
        left_column.template_list(
            'CONV_PIX_WRAPPER_UL_FileEntryItem',
            list_id="ModelBrowser",
            dataptr=self.model_browser_data,
            propname="file_entries",
            active_dataptr=self.model_browser_data,
            active_propname="active_entry",
            rows=20,
            maxrows=20,
        )

        # right browser
        import_anim_row = right_column.row()
        import_anim_row.label(text="Animations to %s:" % usage_type)
        import_anim_row = import_anim_row.row()
        import_anim_row.alignment = "RIGHT"
        import_anim_row.prop(self, "import_animations", text="")

        subpath_row = right_column.row(align=True)
        subpath_row.enabled = False
        subpath_row.prop(self.anim_browser_data, "current_subpath", text="")

        browser_row = right_column.row(align=True)
        browser_row.enabled = self.import_animations
        browser_row.template_list(
            'CONV_PIX_WRAPPER_UL_FileEntryItem',
            list_id="AnimBrowser",
            dataptr=self.anim_browser_data,
            propname="file_entries",
            active_dataptr=self.anim_browser_data,
            active_propname="active_entry",
            rows=20,
            maxrows=20,
        )


class CONV_PIX_WRAPPER_OT_Import(bpy.types.Operator, ImportHelper):
    bl_idname = "converter_pix_wrapper.import"
    bl_label = "Import SCS Models - ConverterPIX & BT (*.scs)"
    bl_description = "Converts and imports selected SCS model with the help of ConvPIX and SCS Blender Tools."
    bl_options = {'UNDO', 'PRESET'}

    directory: StringProperty()

    files: CollectionProperty(name="Selected Files",
                              description="File paths used for importing the SCS files",
                              type=bpy.types.OperatorFileListElement)

    ordered_files = []  # stores ordered list of currently selected files, first selected is first, last selected is last

    archives_to_use: CollectionProperty(name="Archives to Use",
                                        description="Archives that should be used on conversion/import.",
                                        type=ConvPIXWrapperArchiveToUse)

    archives_to_use_mode: BoolProperty(
        default=False,
        description="Add currently selected files to list of archives to be used with ConverterPIX as bases."
    )

    delete_selected_archives_mode: BoolProperty(
        default=False,
        description="Delete selected archives from list."
    )

    move_up_selected_archives_mode: BoolProperty(
        default=False,
        description="Move selected archives up in the list."
    )

    move_down_selected_archives_mode: BoolProperty(
        default=False,
        description="Move selected archives down in the list."
    )

    scs_project_path_mode: BoolProperty(
        default=False,
        description="Set currently selected directory as SCS Project Path"
    )

    only_convert: BoolProperty(
        name="Only convert?",
        description="Use ConverterPIX only for conversion of resources into SCS Project Base Path and import manually later?",
        default=False
    )

    textures_to_base: BoolProperty(
        name="Textures to Base?",
        description="Should textures be copied into the sibling 'base' directory, so they won't be included in mod packing?",
        default=False
    )

    filter_glob: StringProperty(default="*.scs;*.zip;", options={'HIDDEN'})

    def check(self, context):

        # create/update ordered list of currently selected files

        current_file_names = set([file.name for file in self.files])

        # we can put together ordering by copying names into extra array
        for file_name in current_file_names:
            if file_name not in self.ordered_files:
                self.ordered_files.append(file_name)

        # similarly as adding we have to take care of removing items which are not selected anymore
        for file_name in self.ordered_files.copy():  # work upon copy as we are removing items in this for
            if file_name not in current_file_names:
                self.ordered_files.remove(file_name)

        # handle different actions depending on boolean modes variables

        if self.scs_project_path_mode:  # set SCS Project Base Path

            from io_scs_tools.utils import get_scs_globals

            get_scs_globals().scs_project_path = os.path.dirname(self.filepath)
            self.scs_project_path_mode = False

        elif self.archives_to_use_mode:  # add selected archives from browser to archives list

            curr_archives_to_use = [archive.path for archive in self.archives_to_use]

            for file_name in self.ordered_files:

                curr_filepath = path_join(self.directory, file_name)

                # avoid duplicates
                if curr_filepath in curr_archives_to_use:
                    continue

                new_archive_to_use = self.archives_to_use.add()
                new_archive_to_use.path = curr_filepath

            self.archives_to_use_mode = False

        elif self.delete_selected_archives_mode:  # delete selected archives from list

            i = 0
            while i < len(self.archives_to_use):

                if self.archives_to_use[i].selected:
                    self.archives_to_use.remove(i)
                    i -= 1

                i += 1

            self.delete_selected_archives_mode = False

        elif self.move_up_selected_archives_mode:  # move up selected archives in the list

            i = 0
            while i < len(self.archives_to_use):

                if self.archives_to_use[i].selected:

                    if i - 1 >= 0 and not self.archives_to_use[i - 1].selected:
                        self.archives_to_use.move(i, i - 1)

                i += 1

            self.move_up_selected_archives_mode = False

        elif self.move_down_selected_archives_mode:  # move down selected archives in the list

            i = len(self.archives_to_use) - 1
            while i >= 0:

                if self.archives_to_use[i].selected:

                    if i + 1 < len(self.archives_to_use) and not self.archives_to_use[i + 1].selected:
                        self.archives_to_use.move(i, i + 1)

                i -= 1

            self.move_down_selected_archives_mode = False

    def execute(self, context):

        archive_paths = [{"name": archive.path} for archive in self.archives_to_use]

        # additionally add currently selected archives
        for file_name in self.ordered_files:
            archive_paths.append({"name": os.path.join(self.directory, file_name)})

        bpy.ops.converter_pix_wrapper.list_and_import("INVOKE_DEFAULT",
                                                      archive_paths=archive_paths,
                                                      only_convert=self.only_convert,
                                                      textures_to_base=self.textures_to_base)

        return {'FINISHED'}

    def invoke(self, context, event):

        # quick check if BT are installed
        if "io_scs_tools" not in context.preferences.addons:
            self.report({"ERROR"}, "Can't run Converter PIX Wrapper! Please install SCS Blender Tools add-on first & enable it!")
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):

        from io_scs_tools import SCS_TOOLS_OT_Import
        from io_scs_tools.internals.containers.config import AsyncPathsInit
        from io_scs_tools.utils import get_scs_globals

        files_box = self.layout.box()
        files_box.row().label(text="Extra Archives to Use:")

        is_any_archive_selected = False
        files_list_col = files_box.column(align=True)
        if len(self.archives_to_use) > 0:
            for archive in self.archives_to_use:

                row = files_list_col.row(align=True)
                path_col = row.column(align=True)
                path_col.enabled = False
                path_col.prop(archive, "path", text="")
                row.prop(archive, "selected", text="", icon_only=True, icon="CHECKMARK" if archive.selected else "BLANK1")

                is_any_archive_selected |= archive.selected

        else:

            files_list_col.label(text="No extra archives!", icon="INFO")

        # show controls of list only if sth is selected
        if is_any_archive_selected:

            row = files_list_col.row(align=True)
            row.prop(self, "delete_selected_archives_mode", text="Remove", icon="PANEL_CLOSE")
            row.prop(self, "move_up_selected_archives_mode", text="Up", icon="TRIA_UP")
            row.prop(self, "move_down_selected_archives_mode", text="Down", icon="TRIA_DOWN")

        files_list_col.prop(self, "archives_to_use_mode", toggle=True, text="Add Archives to List", icon='PASTEDOWN')

        settings_col = self.layout.box().column(align=True)
        settings_col.prop(self, "only_convert")
        settings_col.prop(self, "textures_to_base")

        if self.only_convert:
            scs_globals = get_scs_globals()

            # importer_version = round(import_pix.version(), 2)
            layout = self.layout

            # SCS Project Path
            box1 = layout.box()
            layout_box_col = box1.column(align=True)
            layout_box_col.label(text='SCS Project Base Path:', icon='FILE_FOLDER')
            layout_box_col.separator()

            layout_box_row = layout_box_col.row(align=True)
            layout_box_row.alert = not os.path.isdir(scs_globals.scs_project_path)
            layout_box_row.prop(scs_globals, 'scs_project_path', text='')

            layout_box_row = layout_box_col.row(align=True)
            layout_box_row.prop(self, "scs_project_path_mode", toggle=True, text="Set Current Dir as Project Base", icon='PASTEDOWN')

            if AsyncPathsInit.is_running():  # report running path initialization operator
                layout_box_row = layout_box_col.row(align=True)
                layout_box_row.label(text="Paths initialization in progress...")
                layout_box_row.label(text="", icon='TIME')
        else:
            SCS_TOOLS_OT_Import.draw(self, context)


class CONV_PIX_WRAPPER_OT_UpdateEXE(bpy.types.Operator):
    bl_idname = "world.converter_pix_wrapper_update_exe"
    bl_label = "Update ConverterPIX Executable"
    bl_description = "Not sure if your ConverterPIX is up-to date? Use this button to download & update it!"
    bl_options = {'INTERNAL'}

    def execute(self, context):

        if update_converter_pix():
            self.report({"INFO"}, "ConverterPIX file updated!")
        else:
            self.report({"ERROR"}, "Problem updating ConverterPIX! Try again later.")

        return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(CONV_PIX_WRAPPER_OT_Import.bl_idname, text="SCS Models - ConverterPIX & BT (*.scs)")


classes = (
    ConvPIXWrapperAddonPrefs,
    ConvPIXWrapperFileEntry,
    ConvPIXWrapperBrowserData,
    ConvPIXWrapperArchiveToUse,

    CONV_PIX_WRAPPER_UL_FileEntryItem,
    CONV_PIX_WRAPPER_OT_ListImport,
    CONV_PIX_WRAPPER_OT_Import,
    CONV_PIX_WRAPPER_OT_UpdateEXE,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # check if converter pix exists or it's not to more than 1 day old, otherwise redownload it!
    if not os.path.isfile(CONVERTER_PIX_PATH) or time() - os.path.getmtime(CONVERTER_PIX_PATH) > 60 * 60 * 24:

        t = Thread(name="update converterpix", target=update_converter_pix)
        t.setDaemon(True)
        t.start()


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == '__main__':
    register()
