## ConverterPIXWrapper
Wrapper add-on to use [ConverterPIX](https://github.com/mwl4/ConverterPIX) within the Blender and import SCS game models with ease.

## Installation & prerequisite
- Go to GitHub latest release page: **[link](../../releases/latest)**.
- Download released ZIP file
- Start Blender
- Open "**User Preferences**"
- On the buttom of the window click "**Install from File...**" and select downloaded ZIP
- Enable the add-on by writting ***ConverterPIX*** in search bar and ticking the checkbox
- Hit "**Save User Settings**"

**NOTE:** If you are experienced user of Blender you can use any other preferred way to install this add-on.

To be able to use ConverterPIXWrapper you will also have to install **SCS Blender Tools** add-on that can be found here: [link](http://modding.scssoft.com/wiki/Documentation/Tools/SCS_Blender_Tools/Download).

## Usage
* Go to menu **File** -> **Import** -> **SCS Models - ConverterPIX & BT (*.scs)**
  ![Import SCS Models](/readme_images/file-import.png)
* After file browser is opened, navigate to *.scs files of SCS Game and select the ones you want to import models from
* Set options by your liking (you can find them on the left bottom side of the file browser window):
  * **Convert only?** - property deciding if add-on will only convert selected model insted of automatically importing it afterwards
  * **SCS Project Base Path** - path where selected model will be extracted and converter. Converted resources will be found under same subfolders as they are in SCS archive.
  * Other options - the rest of the options are SCS Blender Tools import options, more about them: [here](http://modding.scssoft.com/wiki/Documentation/Tools/SCS_Blender_Tools/Import#Import_Options)
* Once happy with the file selection and import options, click **Import SCS Models - ConvPIX & BT (*.scs)** (on right upper side)
* New dialog appears for browsing the archive and selecting the desired model:
   ![Selecting model & animations](/readme_images/archive-window.png)
  * NOTE: Additionally when working with animated model, you can also select animations you want to convert/import (as shown on image).
* When you found a model and selected it, click **OK** to start conversion/import procedure!
