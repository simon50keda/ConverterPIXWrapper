bl_info = {
    "name": "ConverterPIX Wrapper for conversion & import of SCS Game Models",
    "description": "Wrapper add-on to use ConvPIX within the Blender and import SCS game models with ease.",
    "author": "Simon Lusenc (50keda)",
    "version": (1, 0),
    "blender": (2, 78, 0),
    "location": "File > Import > SCS Models - ConverterPIX & BT (*.scs)",
    "category": "Import-Export",
    "support": "COMMUNITY"
}

import bpy
import os
import subprocess
from urllib.request import urlretrieve
from sys import platform
from bpy.props import StringProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty
from bpy.types import AddonPreferences
from bpy_extras.io_utils import ImportHelper

# use blender configuration directories to save converter pix binary,
# this way we can avoid permission problems of saving exe file
CONVERTER_PIX_DIR = os.path.join(bpy.utils.resource_path('USER'), "config/ConverterPIXWrapper")

if not os.path.isdir(CONVERTER_PIX_DIR):
    os.makedirs(CONVERTER_PIX_DIR, exist_ok=True)

CONVERTER_PIX_PATH = os.path.join(CONVERTER_PIX_DIR, "converter_pix.exe")


def path_join(path1, path2):
    """Joins path1 with path2 and replaces backslashes with forward ones.
    Needed for proper navigation inside archive tree on Windows.
    """
    return os.path.join(path1, path2).replace("\\", "/")


def update_converter_pix():
    """Downloads ConverterPIX from github and saves it to CONVERTER_PIX_PATH."""

    print("Downloading ConverterPIX...", end="")
    urlretrieve("https://github.com/mwl4/ConverterPIX/raw/master/bin/win_x86/converter_pix.exe", CONVERTER_PIX_PATH)
    print(" Done!")


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

    if platform == "darwin":
        print("Mac OS X not supported at the moment!")
        return -1, []

    final_command = []

    if platform == "linux":
        final_command.append("wine")  # TODO: maybe better check if wine exists at all?

    final_command.append(CONVERTER_PIX_PATH)

    final_command.extend(args)

    print(final_command)

    result = subprocess.run(final_command, stdout=subprocess.PIPE)

    # if there was some problem running converter pix just return empty list
    if result.returncode != 0:
        return result.returncode, []

    # also return non-zero code if converter pix alone is reporting errors in output
    if "<error>".encode("utf-8") in result.stdout:
        return -1, result.stdout.decode("utf-8").split("\r\n")

    decoded_result = result.stdout.decode("utf-8").split("\r\n")

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


class ConvPIXWrapperFileEntry(bpy.types.PropertyGroup):
    """Property group holding browser file entry data."""

    do_import = BoolProperty(description="Proccess this entry for conversion/import.")
    name = StringProperty(description="Name of the entry represeting name of the file or directory.")
    is_dir = BoolProperty(description="Taging this entry as directory.")


class ConvPIXWrapperBrowserData(bpy.types.PropertyGroup):
    """Property group representing file browser data."""

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

    multi_select = BoolProperty(
        description="Can multiple files be selected?"
    )

    file_extension = StringProperty(
        description="File extension for the files that should be listed in this browser data.",
        default="*",
    )

    archive_paths = CollectionProperty(
        description="Paths to archives from which directories and files should be listed.",
        type=bpy.types.OperatorFileListElement,
    )

    current_subpath = StringProperty(
        description="Current position in archive tree.",
        default="/",
    )

    file_entries = CollectionProperty(
        description="Collection of file entries for current position in archive tree.",
        type=ConvPIXWrapperFileEntry,
    )

    active_entry = IntProperty(
        description="Currently selected directory/file in browser.",
        default=-1,
        update=update_active_entry
    )


class ConvPIXWrapperFileEntryUIListItem(bpy.types.UIList):
    """Class for drawing archive browser file entry."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):

        if item.name == "..":
            icon = "FILE_PARENT"
        elif item.is_dir:
            icon = "FILE_FOLDER"
        else:
            icon = "FILE_BLANK"

        split_line = layout.split(percentage=0.8)
        split_line.prop(item, "name", text="", emboss=False, icon=icon)

        if data.multi_select and not item.is_dir:

            row = split_line.row()
            row.alignment = "RIGHT"
            row.prop(item, "do_import", text="")


class ConvPIXWrapperListImport(bpy.types.Operator):
    bl_idname = "import_mesh.converter_pix_list_and_import"
    bl_label = "Converter PIX Wrapper"
    bl_options = {'UNDO', 'INTERNAL'}

    archive_paths = CollectionProperty(
        description="Paths to archives from which directories and files should be listed.",
        type=bpy.types.OperatorFileListElement,
    )

    only_convert = BoolProperty(
        description="Use ConverterPIX only for conversion of resources into SCS Project Base Path and import manually later?",
    )

    import_animations = BoolProperty(
        name="Use Animations",
        description="Select animations for conversion and import?\n"
                    "Gives you ability to convert and import animations for selected model (use it only if you are working with animated model)."
    )

    model_browser_data = PointerProperty(
        description="Archive browser data for model selection.",
        type=ConvPIXWrapperBrowserData
    )

    anim_browser_data = PointerProperty(
        description="Archive browser data for animations selection.",
        type=ConvPIXWrapperBrowserData
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

        self.model_browser_data.file_extension = ".pmg"
        self.anim_browser_data.file_extension = ".pma"

        self.anim_browser_data.multi_select = True

        self.model_browser_data.update_active_entry(context)
        self.anim_browser_data.update_active_entry(context)

        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):

        from io_scs_tools.utils import get_scs_globals

        model_file_entry_name = self.model_browser_data.file_entries[self.model_browser_data.active_entry].name
        model_archive_subpath = path_join(self.model_browser_data.current_subpath, model_file_entry_name)

        # collect all selected animations from animations browser
        anim_archive_subpaths = []
        if self.import_animations:

            for anim_file_entry in self.anim_browser_data.file_entries:
                if anim_file_entry.do_import:
                    anim_archive_subpaths.append(path_join(self.anim_browser_data.current_subpath, anim_file_entry.name[:-4]))

        # put together arguments for converter pix
        args = []

        for archive_path in self.archive_paths:
            args.extend(["-b", archive_path.name])

        args.extend(["-m", model_archive_subpath[:-4]])
        args.extend(anim_archive_subpaths)
        args.extend(["-e", get_scs_globals().scs_project_path])

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

        # now do actual import with BT
        if not self.only_convert:

            pim_import_file = model_file_entry_name[:-4] + ".pim"
            pim_import_dir = path_join(get_scs_globals().scs_project_path, self.model_browser_data.current_subpath[1:])

            bpy.ops.import_mesh.pim(files=[{"name": pim_import_file}], directory=pim_import_dir)

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout

        archive_names = [os.path.basename(archive_path.name) for archive_path in self.archive_paths]
        layout.label("Currently working upon: %r." % archive_names)

        browser_layout = layout.split(percentage=0.5)

        left_column = browser_layout.column(align=True)
        right_column = browser_layout.column(align=True)

        usage_type = "convert" if self.only_convert else "convert & import"

        left_column.label("Model to %s:" % usage_type)
        subpath_row = left_column.row(align=True)
        subpath_row.enabled = False
        subpath_row.prop(self.model_browser_data, "current_subpath", text="")
        left_column.template_list(
            'ConvPIXWrapperFileEntryUIListItem',
            list_id="ModelBrowser",
            dataptr=self.model_browser_data,
            propname="file_entries",
            active_dataptr=self.model_browser_data,
            active_propname="active_entry",
            rows=20,
            maxrows=20,
        )

        import_anim_split = right_column.split(percentage=0.9)
        import_anim_split.label("Animations to %s:" % usage_type)
        import_anim_row = import_anim_split.row()
        import_anim_row.alignment = "RIGHT"
        import_anim_row.prop(self, "import_animations", text="")

        subpath_row = right_column.row(align=True)
        subpath_row.enabled = False
        subpath_row.prop(self.anim_browser_data, "current_subpath", text="")

        browser_row = right_column.row(align=True)
        browser_row.enabled = self.import_animations
        browser_row.template_list(
            'ConvPIXWrapperFileEntryUIListItem',
            list_id="AnimBrowser",
            dataptr=self.anim_browser_data,
            propname="file_entries",
            active_dataptr=self.anim_browser_data,
            active_propname="active_entry",
            rows=20,
            maxrows=20,
        )


class ConvPIXWrapperArchiveToUse(bpy.types.PropertyGroup):
    """Property group holding entry data for archives to use."""

    path = StringProperty(description="Path to archive.")
    selected = BoolProperty(description="Marking this path as selected. Once selected it can be deleted or moved in the list.")


class ConvPIXWrapperImport(bpy.types.Operator, ImportHelper):
    bl_idname = "import_mesh.converter_pix_import"
    bl_label = "Import SCS Models - ConverterPIX & BT (*.scs)"
    bl_description = "Converts and imports selected SCS model with the help of ConvPIX and SCS Blender Tools."
    bl_options = {'UNDO', 'PRESET'}

    directory = StringProperty()

    files = CollectionProperty(name="Selected Files",
                               description="File paths used for importing the SCS files",
                               type=bpy.types.OperatorFileListElement)

    archives_to_use = CollectionProperty(name="Archives to Use",
                                         description="Archives that should be used on conversion/import.",
                                         type=ConvPIXWrapperArchiveToUse)

    archives_to_use_mode = BoolProperty(
        default=False,
        description="Add currently selected files to list of archives to be used with ConverterPIX as bases."
    )

    delete_selected_archives_mode = BoolProperty(
        default=False,
        description="Delete selected archives from list."
    )

    move_up_selected_archives_mode = BoolProperty(
        default=False,
        description="Move selected archives up in the list."
    )

    move_down_selected_archives_mode = BoolProperty(
        default=False,
        description="Move selected archives down in the list."
    )

    scs_project_path_mode = BoolProperty(
        default=False,
        description="Set currently selected directory as SCS Project Path"
    )

    only_convert = BoolProperty(
        name="Only convert?",
        description="Use ConverterPIX only for conversion of resources into SCS Project Base Path and import manually later?"
    )

    filter_glob = StringProperty(default="*.scs;", options={'HIDDEN'})

    def check(self, context):

        if self.scs_project_path_mode:  # set SCS Project Base Path

            from io_scs_tools.utils import get_scs_globals

            get_scs_globals().scs_project_path = os.path.dirname(self.filepath)
            self.scs_project_path_mode = False

        elif self.archives_to_use_mode:  # add selected archives from browser to archives list

            curr_archives_to_use = [archive.path for archive in self.archives_to_use]

            for file in self.files:

                curr_filepath = path_join(self.directory, file.name)

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
        bpy.ops.import_mesh.converter_pix_list_and_import("INVOKE_DEFAULT", archive_paths=archive_paths, only_convert=self.only_convert)

        return {'FINISHED'}

    def invoke(self, context, event):

        # quick check if BT are installed
        if "io_scs_tools" not in context.user_preferences.addons:
            self.report({"ERROR"}, "Can't run Converter PIX Wrapper! Please install SCS Blender Tools add-on first & enable it!")
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):

        from io_scs_tools.utils import get_scs_globals
        from io_scs_tools.operators.world import SCSPathsInitialization
        from io_scs_tools import ImportSCS

        files_box = self.layout.box()
        files_box.row().label("Archives to Use:")

        is_any_archive_selected = False
        files_list_col = files_box.column(align=True)
        if len(self.archives_to_use) > 0:
            for archive in self.archives_to_use:

                row = files_list_col.row(align=True)
                path_col = row.column(align=True)
                path_col.enabled = False
                path_col.prop(archive, "path", text="")
                row.prop(archive, "selected", text="", icon_only=True, icon="FILE_TICK" if archive.selected else "BLANK1")

                is_any_archive_selected |= archive.selected

        else:

            files_list_col.label("No archives, at least one needed!", icon="ERROR")

        # show controls of list only if sth is selected
        if is_any_archive_selected:

            row = files_list_col.row(align=True)
            row.prop(self, "delete_selected_archives_mode", text="Remove", icon="PANEL_CLOSE")
            row.prop(self, "move_up_selected_archives_mode", text="Up", icon="TRIA_UP")
            row.prop(self, "move_down_selected_archives_mode", text="Down", icon="TRIA_DOWN")

        files_list_col.prop(self, "archives_to_use_mode", toggle=True, text="Add Archives to List", icon='SCREEN_BACK')

        self.layout.box().prop(self, "only_convert")

        if self.only_convert:
            scs_globals = get_scs_globals()

            # importer_version = round(import_pix.version(), 2)
            layout = self.layout

            # SCS Project Path
            box1 = layout.box()
            layout_box_col = box1.column(align=True)
            layout_box_col.label('SCS Project Base Path:', icon='FILE_FOLDER')

            layout_box_row = layout_box_col.row(align=True)
            layout_box_row.alert = not os.path.isdir(scs_globals.scs_project_path)
            layout_box_row.prop(scs_globals, 'scs_project_path', text='')

            layout_box_row = layout_box_col.row(align=True)
            layout_box_row.prop(self, "scs_project_path_mode", toggle=True, text="Set Current Dir as Project Base", icon='SCREEN_BACK')

            if SCSPathsInitialization.is_running():  # report running path initialization operator
                layout_box_row = layout_box_col.row(align=True)
                layout_box_row.label("Paths initialization in progress...")
                layout_box_row.label("", icon='TIME')
        else:
            ImportSCS.draw(self, context)


class ConvPIXWrapperAddonPrefs(AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("world.update_converter_pix_exe", icon="URL")


class ConvPIXWrapperUpdateEXE(bpy.types.Operator):
    bl_idname = "world.update_converter_pix_exe"
    bl_label = "Update ConverterPIX Executable"
    bl_description = "Not sure if your ConverterPIX is up-to date? Use this button to download & update it!"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            update_converter_pix()
            self.report({"INFO"}, "ConverterPIX file updated!")
        except:
            self.report({"ERROR"}, "Problem updating ConverterPIX! Try again later.")

        return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(ConvPIXWrapperImport.bl_idname, text="SCS Models - ConverterPIX & BT (*.scs)")


def register():
    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_file_import.append(menu_func_import)

    # check if converter pix exists, otherwise download it!
    if not os.path.isfile(CONVERTER_PIX_PATH):
        update_converter_pix()


def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_import.remove(menu_func_import)


if __name__ == '__main__':
    register()
