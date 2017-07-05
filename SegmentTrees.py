import arcpy
import time
import os

# import current vegetation
# import workspace for exit

veg = arcpy.GetParameterAsText(0) # point cloud
pntheight = arcpy.GetParameterAsText(1) # Height field for tree
seeds = arcpy.GetParameterAsText(2) #seed points
scratch = arcpy.GetParameterAsText(3) # scratch workspace
dist = arcpy.GetParameter(4) # Distance for tree to grow each round- Double, default 0.2
height = arcpy.GetParameter(5) # minimum threshold for tree- Double, default 1.0
addLowPoints= arcpy.GetParameterAsText(6) # True/false boolean for whether or not you want to add pts below height threshold back in
outputseg = arcpy.GetParameter(7) # output segmented file

# define a location for the output file
outputvegspace = (arcpy.Describe(outputseg)).path
outputveg = (arcpy.Describe(outputseg)).file

# Checking to see if field already exists
def FieldExist(featureclass, fieldname):
    fieldList = arcpy.ListFields(featureclass, fieldname)
    fieldCount = len(fieldList)
    if (fieldCount == 1):
        return True
    else:
        return False

# Calculates time for each loop. 
def calculatetime(Start, End):
	m, s = divmod((End-Start), 60)
	h,m = divmod(m, 60)
	return "%d:%02d:%02d"%(h, m, s)

def findmax(fc, field):
    maxcursor= arcpy.da.SearchCursor(fc, field)
    maxlist=[]
    for row in maxcursor:
        maxlist.append(row[0])
    return max(maxlist) 


###-----Start the script!---###


# Slice bottom off of point cloud to cut down on time. Create unique names just in case. Put this as a new feature class in the scratch workspace
sl_veg=arcpy.CreateUniqueName("SlicedPointCloud", scratch)
out_sl=sl_veg.replace("\\","/").rsplit("/", 1)[1]
slicedveg= arcpy.FeatureClassToFeatureClass_conversion(veg, scratch, out_sl, "%s>%s"%(pntheight, height))
low_pts=arcpy.CreateUniqueName("LowSliced")
out_low=low_pts.replace("\\","/").rsplit("/", 1)[1]
missing=arcpy.FeatureClassToFeatureClass_conversion(veg, scratch, out_low, "%s<%s"%(pntheight, height))

# Check if trees have already been labelled. If not, add a field name, and create variable for field
# This check means that the tool can be repeated on the segmented feature class
# for example, if you wanted to start the segmentation with a small growth value to capture small scale changes and then re-run with a larger growth value
if (not FieldExist(slicedveg, "TREE_ID")):
    arcpy.Near_analysis(slicedveg, seeds, dist) #If trees haven't been labelled, we'll have to start with a 'NEAR' in 2d.
    arcpy.AddField_management(slicedveg, "TREE_ID", "LONG", 4)
    arcpy.CalculateField_management(slicedveg, "TREE_ID", "!NEAR_FID!", "PYTHON_9.3")
    arcpy.AddField_management(slicedveg, "Growth", "LONG", 4)
    count_var=0
    #repeat_var="FALSE"
    arcpy.AddMessage("This is the first time segmenting trees. Added TreeID field and starting segmentation.")
else:
    # find maximum growth count
    count_var= findmax(slicedveg, "Growth")
    ### missing=arcpy.FeatureClassToFeatureClass_conversion(veg, scratch, "MISSING", "%s<%s"%(pntheight, height))
    #repeat_var="TRUE"
    arcpy.AddMessage("This is an additional segmentation. Starting growth at count=%s"%count_var)



# create feature layer that represents labelled features
arcpy.MakeFeatureLayer_management(slicedveg, "veg_layer")
forest = "veg_layer"

#select points that are labeled
arcpy.SelectLayerByAttribute_management(forest, "NEW_SELECTION", '''"TREE_ID"<>-1''')

#define starting parameters
growthcount = int(arcpy.GetCount_management(forest).getOutput(0))
arcpy.AddMessage("After 2d trunk detection, there are %s points labelled"%growthcount)
Segmented = arcpy.FeatureClassToFeatureClass_conversion(forest, outputvegspace, outputveg)
arcpy.CalculateField_management(Segmented, "Growth", 0, "PYTHON_9.3")
growth =Segmented # start growth off with this, then replace it with newer growths



# while there is new growth...
while growthcount>0:
    starttime=time.clock()
    count_var+=1

    # Create dictionary that has object ids and the labels associated
    # This will be a reference for all the points with their associated labels
    TreeDictionary = {}
    MyCursor = arcpy.SearchCursor(growth)
    for Feature in MyCursor:
        TreeDictionary[Feature.getValue("OBJECTID")] = Feature.getValue("TREE_ID")
    del Feature
    del MyCursor

    #Delete previous growth from the forest
    arcpy.DeleteFeatures_management(forest)

    # Run Near from the currently labeled points to the overall data
    arcpy.Near3D_3d(forest, growth, dist)

    
    # Label the new growth using the dictionary
    arcpy.SelectLayerByAttribute_management(forest, "NEW_SELECTION", ' "NEAR_FID"<>-1')
    with arcpy.da.UpdateCursor(forest, ['TREE_ID', 'NEAR_FID', 'Growth']) as cursor:
        for row in cursor:
            row[0]=TreeDictionary[row[1]]
            row[2]=count_var
            cursor.updateRow(row)            
    del TreeDictionary

    # Create new growth feature
    scratch_feature= "VegGrowth_%s"%count_var
    growth = arcpy.FeatureClassToFeatureClass_conversion(forest, scratch, scratch_feature)
    growthcount =int(arcpy.GetCount_management(growth).getOutput(0))

    # Add the growth to the Segmented class
    arcpy.Append_management(growth, Segmented, "NO_TEST")
    
    endtime=time.clock()
    arcpy.AddMessage("Loop %s finished in %s, and %s new points labelled"%(count_var, calculatetime(starttime, endtime), growthcount))



# Add the unlabeled points to the segmented
arcpy.SelectLayerByAttribute_management(forest, "CLEAR_SELECTION")

if (addLowPoints=='true'): #if below height should be added
    arcpy.Append_management([slicedveg, missing], Segmented, "NO_TEST")
    
else:
    arcpy.Append_management(slicedveg, Segmented, "NO_TEST")

#Delete growth
arcpy.env.workspace= scratch
growthlist=arcpy.ListFeatureClasses("VegGrowth_*")
for growthfeatures in growthlist:
    arcpy.Delete_management(growthfeatures)

# delete sliced point cloud
arcpy.Delete_management(slicedveg)
