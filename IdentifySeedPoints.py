# Tool for generating seed points with user defined bin sizes.

import arcpy
import math
from arcpy import env
from arcpy.sa import *

# import variables for analysis
veg= arcpy.GetParameterAsText(0) # non ground point cloud
height_field= arcpy.GetParameterAsText(1) # height field with height from DEM
seedname = arcpy.GetParameterAsText(2)  # output file location for seeds
scratch = arcpy.GetParameterAsText(3) # scratch workspace for rasters

pt_spacing= arcpy.GetParameter(4) # point spacing from .LAS file
slices = arcpy.GetParameter(5) # list of all slices including lower and upper bounds. Multivalue double: Default is 1, 2, 4, 10
num_needed = arcpy.GetParameter(6) # number of slices needed for tree to exist. Default is 4


# Create a sorted list out of the slices based on their number
# Then create a list of tuples that will define the bin sizes-- (1,2), (2,4), etc...
slicesorted = sorted(slices)
slicelist = zip(slicesorted, slicesorted[1:])



arcpy.MakeFeatureLayer_management(veg, "veg_layer")
forest = "veg_layer"
arcpy.env.workspace = scratch
slcount=0
cell_size = pt_spacing*4 # Based on ESRI White Paper
RasList= []
var_dic={}


for lo, hi in slicelist:
    slcount +=1

    # select all points in slice
    whereclause = '''"%s"<%s AND "%s">%s'''%(height_field, hi, height_field, lo)
    arcpy.SelectLayerByAttribute_management(forest, "NEW_SELECTION", whereclause)

    # generate raster of selection
    outras = "Slice_%s"%slcount
    arcpy.PointToRaster_conversion(forest, height_field, outras, "MEAN", "", cell_size)

    # Expand raster by one cell? sure why not.
    outname="Expanded_%s"%slcount
    expanded_raster=arcpy.sa.Expand(arcpy.sa.Int(outras), 1, slcount)
    #arcpy.RasterToPolygon_conversion(expanded_raster, outname, "NO_SIMPLIFY")
    expanded_raster.save(outname)

    # Add raster to raster list so it can be manipulated with the rest
    RasList.append(outname)
    arcpy.AddMessage(slcount)



# Calculate stats on all expanded rasters
fcs=arcpy.ListRasters("Expanded*")

cellstatrast= arcpy.sa.CellStatistics(fcs, "VARIETY")

cellstatrast.save("Cell_Variety_01")


# IN FUTURE: Add another 'expand' step, with weight towards higher values

out_poly= "Tree_polygons"

# Convert to polygon
# Merge adjacent polygons with value greater than X number of slices (default 4)
# get centerpoint and save as seedpoints

arcpy.RasterToPolygon_conversion(cellstatrast, out_poly, "SIMPLIFY", "Value")

arcpy.MakeFeatureLayer_management(out_poly, "poly_layer")
polylr = "poly_layer"
arcpy.SelectLayerByAttribute_management(polylr, "NEW_SELECTION", "gridcode=%s"%num_needed)
thiscount=int(arcpy.GetCount_management(polylr).getOutput(0))
arcpy.AddMessage(thiscount)

arcpy.AggregatePolygons_cartography(polylr, "merge_poly", cell_size, pt_spacing)

arcpy.FeatureToPoint_management("merge_poly", seedname, "CENTROID")
