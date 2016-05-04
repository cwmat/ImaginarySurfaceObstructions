"""
Imaginary Surface Obstruction Analysis
POC - chaz.mateer@gmail.com

Python Script that requires the arcpy module and the advanced license.  Created to analyze obstructions in the approach surfaces.

Still in progress.  Comments and docstrings are not complete but the program works.

Arguments (script tool data type):

Preconditions:



"""
## Potential functions
# Buffer line 8,001 feet

# Check that data have linear units in feet

# Parse int

# Check if string

# Check for feet as linear unit

# Extract by mask

# Unify SRS

# Select obs

# Handle GDB name maybe just let user define name

# Maybe add an erase routine for incorrect primary surfaces - consider z values

# Estimate potential error based on difference in DEM elevation along runway and into runway value

# Check color maps and raster fucntions


# Import modules
import os
import sys
import arcpy
from arcpy.sa import *
import traceback

# Global constants
TEMP_FEATURES = []
EUC_DIST = 15000
SLOPE_RATIO = 50
MOSAIC_LIST = []

# Check for ArcAdvanced license
def has_advanced():
    """
    TODO

    """
    if arcpy.ProductInfo() == "ArcInfo":
        return True
    else:
        return False

# Get unique analysis ID
def get_UID(input_data, fields):
    """
    TODO

    """
    analysis_id_list = []
    with arcpy.da.SearchCursor(input_data, fields, sql_clause=("DISTINCT", None)) as cursor:
        for row in cursor:
            analysis_id_list.append(row[0])

    return analysis_id_list

# Produce flat buffers from lines
def make_flat_buffers(prim_surface, id_field):
    """
    TODO

    """
    output = "prim_buffer"
    distance = "8001 Feet"
    line_type = "FLAT"
    dissolve = "LIST"
    arcpy.Buffer_analysis(prim_surface, output, distance, line_end_type=line_type, dissolve_option=dissolve, dissolve_field=[id_field])
    add_temp(output)
    return output

def crack_layers(analysis_id_list, approach_surface, app_analysis_id_field, primary_surface, prim_analysis_id_field, analysis_dict):
    """
    TODO

    """
    # TODO this will fail if user has an ID field that is a string
    for analysis_id in analysis_id_list:
        arcpy.AddMessage("Analysis ID {0} found...".format(analysis_id))
        temp_app_lyr = "temp_app_lyr"
        temp_prim_lyr = "temp_prim_lyr"
        app_name = "ApproachSurface_ID{0}".format(analysis_id)
        prim_name = "PrimarySurface_ID{0}".format(analysis_id)
        appr_clause = """{0} = {1}""".format(arcpy.AddFieldDelimiters(approach_surface, app_analysis_id_field), analysis_id)
        prim_clause = """{0} = {1}""".format(arcpy.AddFieldDelimiters(primary_surface, prim_analysis_id_field), analysis_id)

        # Make query layer using analysis ID
        arcpy.MakeFeatureLayer_management(approach_surface, temp_app_lyr, appr_clause)
        arcpy.MakeFeatureLayer_management(primary_surface, temp_prim_lyr, prim_clause)

        # Copy layers to new dataset and add to dict
        arcpy.CopyFeatures_management(temp_app_lyr, app_name)
        arcpy.CopyFeatures_management(temp_prim_lyr, prim_name)
        key_name = "Analysis_ID_{0}".format(analysis_id)
        analysis_dict[key_name] = {"appr": app_name, "prim": prim_name}

        # Clean up
        add_temp(app_name)
        add_temp(prim_name)
        arcpy.Delete_management(temp_app_lyr)
        arcpy.Delete_management(temp_prim_lyr)

# Convert obstruction points to raster
def convert_obs(obs, height_field, dem):
    """
    TODO

    """
    # Need to handle name
    temp_output = "temp_obs"
    output = "Obstructions_Raster"
    arcpy.PointToRaster_conversion(obs, height_field, temp_output)
    temp_plus = Plus(Raster(temp_output), Raster(dem))
    temp_plus.save(output)
    add_temp(temp_output)
    add_temp(output)

    return Raster(output)

# Euclidean
def run_euclidean_analysis(appr, prim, runway, obs, output_name):
    """
    TODO

    """
    desc = arcpy.Describe(appr)
    ext = desc.extent
    arcpy.env.extent = ext
    temp_euc = EucDistance(prim, EUC_DIST)
    temp_extract = ExtractByMask(temp_euc, appr)
    arcpy.env.extent = "MAXOF"
    temp_divide = Divide(temp_extract, 50)
    temp_plus = Plus(temp_divide, runway)
    temp_subtract = Minus(temp_plus, obs)
    # Flip the symbol so negative does not intersect and positive does
    temp_times = Times(temp_subtract, -1.0)
    temp_times.save(output_name)
    MOSAIC_LIST.append(output_name)

    # Cleanup
    add_temp(output_name)
    lyr_list = [temp_euc, temp_extract, temp_divide, temp_plus, temp_subtract]
    for lyr in lyr_list:
        arcpy.Delete_management(lyr)

# Append or extend TEMP_FEATURES
def add_temp(feature):
    """
    TODO

    """
    if feature is list:
        for item in feature:
            add_temp(item)
    else:
        TEMP_FEATURES.append(feature)

def clean_temp():
    """
    TODO

    """
    try:
        for item in TEMP_FEATURES:
            arcpy.Delete_management(item)
        return True
    except Exception, e:
        arcpy.AddMessage(e)
        return False

# Main method
def execute():
    # Check out extension
    arcpy.AddMessage("Checking for Spatial Analyst Extension")
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        arcpy.AddMessage("You need access to Spatial Analyst for this tool.  Exiting tool.")
        sys.exit(1)

    # Check if user is running ArcAdvanced, quit if not
    arcpy.AddMessage("Checking for ArcAdvanced License")
    if not has_advanced():
        arcpy.AddMessage("You are not currently running ArcAdvanced.  This tool will now exit.")
        sys.exit(1)

    # Unpack arguments
    runway_alt = int(arcpy.GetParameter(0))
    approach_surface = arcpy.GetParameterAsText(1)
    app_analysis_id_field = arcpy.GetParameterAsText(2)
    primary_surface = arcpy.GetParameterAsText(3)
    prim_analysis_id_field = arcpy.GetParameterAsText(4)
    dem = arcpy.GetParameterAsText(5)
    obs = arcpy.GetParameterAsText(6)
    obs_height_field = arcpy.GetParameterAsText(7)
    output_folder = arcpy.GetParameterAsText(8)
    gdb_name = arcpy.GetParameterAsText(9)
    clean_up = arcpy.GetParameter(10)

    # Instantiate local variables
    output_gdb = os.path.join(output_folder, gdb_name + ".gdb")
    analysis_id_list = None
    analysis_dict = {}

    # Create output gdb and set environment settings TODO add name handler
    arcpy.AddMessage("Creating output workspace...")
    arcpy.env.overwriteOutput = True
    arcpy.CreateFileGDB_management(output_folder, gdb_name)
    arcpy.env.workspace = output_gdb

    # Buffer the prim lines and save over old var
    arcpy.AddMessage("Creating flat buffers...")
    primary_surface = make_flat_buffers(primary_surface, prim_analysis_id_field)

    # Get analysis IDs
    arcpy.AddMessage("Retrieving Analysis IDs from inputs...")
    analysis_id_list = get_UID(approach_surface, [app_analysis_id_field])

    # Crack input layers TODO this will fail if user has an ID field that is a string
    crack_layers(analysis_id_list, approach_surface, app_analysis_id_field, primary_surface, prim_analysis_id_field, analysis_dict)

    # Create obstructions raster
    arcpy.AddMessage("Creating obstructions raster...")
    obs_raster = convert_obs(obs, obs_height_field, dem)

    # Conduct euclidean analysis
    arcpy.AddMessage("Running main obstruction analysis...")
    for key in analysis_dict.keys():
        arcpy.AddMessage("Processing for {0}...".format(key))
        appr_analysis = analysis_dict[key]["appr"]
        prim_analysis = analysis_dict[key]["prim"]
        output_name = "Output_{0}".format(key)

        run_euclidean_analysis(appr_analysis, prim_analysis, runway_alt, obs_raster, output_name)

    # Mosaic the output together
    arcpy.AddMessage("Mosaicing final output...")
    final_output = "Obstruction_Analysis_Final"
    arcpy.MosaicToNewRaster_management(MOSAIC_LIST, output_gdb, final_output, pixel_type="64_BIT", number_of_bands=1)

    # Clean up temporary files if the clean_up var is true
    if clean_up:
        arcpy.AddMessage("Attempting to clear out temporary files...")
        temp_is_clean = clean_temp()
        if temp_is_clean:
            arcpy.AddMessage("All temporary files removed from workspace!")
        else:
            arcpy.AddMessage("There was a non-critical error and not all temporary files were removed from workspace.")
            arcpy.AddMessage(TEMP_FEATURES)

    # Check extension back in
    arcpy.CheckInExtension("Spatial")

if __name__ == '__main__':
    try:
        execute()
    except Exception, e:
        arcpy.AddMessage("OPERATION FAILED!")
        arcpy.AddMessage(e)
        arcpy.AddMessage(traceback.format_exc())
