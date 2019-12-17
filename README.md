## ConverterPIXWrapper
Wrapper add-on to use [ConverterPIX](https://github.com/mwl4/ConverterPIX) within the Blender and import SCS game models with ease.

## Installation & prerequisites
- Go to GitHub latest release page: [link](../../releases/latest).
- Download released ZIP file: **io_converter_pix_wrapper.zip**
- Start Blender
- Open "**User Preferences**"
- On the buttom of the window click "**Install from File...**" and select downloaded ZIP
- Enable the add-on by writting "***ConverterPIX***" in search bar and ticking the checkbox
- Hit "**Save User Settings**", done!

**NOTE:** If you are experienced user of Blender you can use any other preferred way to install this add-on.

To be able to use ConverterPIXWrapper you will also have to install **SCS Blender Tools** add-on that can be found here: [link](http://modding.scssoft.com/wiki/Documentation/Tools/SCS_Blender_Tools/Download).

## Usage
* Go to menu "**File**" -> "**Import**" -> "**SCS Models - ConverterPIX & BT (*.scs)**"
  ![Import SCS Models](/readme_images/file-import.png)
* After file browser is opened, navigate to *.scs files of SCS Game or *.zip files of any mod and select ones you want to import from.
* Now set the rest of the options by your liking (you can find them on the left bottom side of the file browser window):
  * **Extra Archives to Use** - storage for archives from multiple locations. More info down below at: [Additional Usage Tips](#additional-usage-tips)
  * **Convert only?** - property deciding if add-on will only convert selected model insted of automatically importing it afterwards
  * **SCS Project Base Path** - path where selected model will be extracted and converter. Converted resources will be found under same subfolders as they are in SCS archive.
  * Other options - the rest of the options are SCS Blender Tools import options, more about them: [here](http://modding.scssoft.com/wiki/Documentation/Tools/SCS_Blender_Tools/Import#Import_Options)
* Once happy with the archive list and import options, click "**Import SCS Models - ConvPIX & BT (*.scs)**" (on right upper side)
* New dialog appears for browsing the archive and selecting the desired model:
   ![Selecting model & animations](/readme_images/archive-window.png)
  * NOTE: Additionally when working with animated model, you can also select animations you want to convert/import (as shown on image).
* When you found a model and selected it, click button "**OK**" to start conversion/import procedure!

## Additional Usage Tips
One of extra features are **Extra Archives**. Extra archives give you ability to import from multiple archives originating from different locations on your disc.

![Add Archives To List](/readme_images/select-scs-archives.png)

This is very useful if you are importing from mod that is dependent on vanilla data. In that case you can search for "base.scs", select and add it to extra archives using **Add Archives to List**. After that you only search for a mod archive, select it and proced with importing.

Extra archives list additionally enables you to remove or change order of added items:

![Archive List Handling](/readme_images/archive-list-handling.png)

To do that, you have to use selection buttons on side of each entry (check mark arrow marks item as selected) and then desired actions can be executed upon them. Moving items will change the order how archives will be passed to ConverterPIX as base. First item in the list is given first, last item is given as last.
