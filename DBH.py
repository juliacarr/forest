# Calculates DBH and flags problematic points
from numpy import sin, cos, radians, arctan, degrees, sqrt, mean
from collections import defaultdict
from math import pi

veg = arcpy.GetParameterAsText(0) # Point cloud
HeightField = arcpy.GetParameterAsText(1) # Height field derived from point cloud
treeid = arcpy.GetParameterAsText(2) #Tree label field
seeds = arcpy.GetParameterAsText(3) #Seed points
diameterThreshold = arcpy.GetParameter(4) #Tree radius that seems legit
nearangle = arcpy.GetParameter(5) # angle for general branch angle
slices = arcpy.GetParameter(6) # list of all slices including lower and upper bounds. Multivalue double: Default is 1, 2, 4, 10
scratch=arcpy.GetParameterAsText(7) #scratch workspace


# ------------------------------------------------------
# Define functions for dealing with angles and finding outliers

#Set of functions to get the average angle in degrees. Takes in a list as a parameter
def cosx(lst):
    return [cos(radians(x)) for x in lst]
def sinx(lst):
    return [sin(radians(x)) for x in lst]

# Finds average angle in degrees. If for some reason the points are EXACTLY evenly spaced, will return '999', which is out of bounds
def averageangles(lst):
    if (len(lst)==0):
        return 998
    else:
	avx = sum(cosx(lst))/len(lst)
	avy= sum(sinx(lst))/len(lst)
	r=sqrt((avx**2)+(avy**2))
	avcos=avx/r
	avsin=avy/r
	if (r<0.00000001):
		return 999
	else:
		avtheta=arctan(avsin/avcos)
		theta= degrees(avtheta)
		if ((avsin>0) and (avcos>0)):
			angle= theta
		elif((avsin<0) and (avcos>0)):
			angle= 360+theta
		else:
			angle= 180+theta
		return angle

# Test if a test angle is within a range of an input angle
def AngleIsNear(test, inangle, rangenum):
	badnum=360-rangenum
	if (inangle >= badnum): 
		lo= inangle-rangenum
		hi = inangle+rangenum-360
		if (lo<test or test<hi):
			return True
		else:
			return False
	elif(inangle<=rangenum):
		lo= inangle-rangenum +360
		hi = inangle+rangenum
		if (lo<test or test<hi):
			return True
		else:
			return False
	else:
		lo = inangle-rangenum
		hi = inangle+rangenum
		if (lo<test<hi):
			return True
		else:
			return False

# Get the standard deviation of a list of distances
def standarddev(lst):
    squared=map(lambda x:x**2, lst)
    means=mean(squared)
    dev=sqrt(means)
    return dev


# This identifies distances and angles that are out of the expected range and identifies them as 'outliers'
def LabelOutliers(fc, label):
    tlist=[] #Tree list
    dlist=[] #Distance List
    alist=[] #Angle List

    # Create a list of trees and of distances
    trows= arcpy.da.SearchCursor(fc, [label, "NEAR_DIST", "NEAR_ANGLE"])
    for r in trows:
        tlist.append(r[0])
        dlist.append(r[1])
        alist.append(r[2])

    # Zip together the two lists into a list of tuples. This will pair each distance with its tree label.
    distlist=zip(tlist, dlist)
    anglelist=zip(tlist, alist)

    #Create a dictionary that has distance-angle pairs.
    distanglelist=zip(dlist, alist)
    distbyangle={}
    for d, a in distanglelist:
        distbyangle[d]=a

    
    #Sort the values in ascending order
    #Add to dictionary. This means that every dictionary key will be a tree, with a sorted list of all of its distances
    distbytree= defaultdict(list)
    sortedlist=sorted(distlist)
    for (t, d) in sortedlist:
        distbytree[t].append(d)

    # Create list that will hold all the standard deviations for each tree
    deviationlist=[]
        
    # We have a dictionary of each tree, then an ascending list of its values.
    # Calculate standard deviation for each set of distances, and create a list with the values outside of stdev
    for tree, distancelist in distbytree.iteritems():
        mydev = standarddev(distancelist)
        if mydev>(diameterThreshold/2): 
            deviationlist.append(tree)

       
    # Also have a dictionary with all angles that have a tree outside of radius threshold
    anglebytree=defaultdict(list)
    for t, a in anglelist:
        if t in deviationlist:
            anglebytree[t].append(a)
            
    
    averageangledict={}
    #Calculate average angle for each tree outside of threshold, then create list for points within branch
    for mytree, ang in anglebytree.iteritems():
        averageangledict[mytree]= averageangles(ang)
        branchlist=[x for x in ang if AngleIsNear(x, averageangledict[mytree], nearangle)]
        anglebytree[mytree]=branchlist
        
    # Recheck the standard deviation for each tree WITHOUT angle points
    # Label as '1' anything within standard deviation
    for atree, adistlist in distbytree.iteritems():
        # For each tree, find points that have problematic angles. 
        #looking for each DISTANCE value within each DISTANCELIST, and then
        # checking if the corresponding ANGLE is a problem angle.
        anglesnear=[angle for angle in anglebytree[atree]]
        branchlist=[bd for bd in adistlist if distbyangle[bd] in anglesnear]

        # now switch to those remaining:
        trunklist=[t for t in adistlist if t not in branchlist]

        # calculate the standard deviation of remaining points
        trunkdev=standarddev(trunklist)
        fulldev=standarddev(adistlist)

        #cut the tree dictionary for ALL points by the standard deviation of points minus the problem branch
        cutlist = [x for x in distbytree[atree] if x>trunkdev]
        distbytree[atree]=cutlist

    
    # Label every tree that is greater than one stdev away    
    with arcpy.da.UpdateCursor(fc, [label, 'NEAR_DIST','NEAR_ANGLE', 'InRange']) as cursor:
        for row in cursor:
            # for each tree-dist pair in the list, label InRange as 0
            # if not in list, label as 1
            if (row[2] in anglebytree[row[0]]):
                row[3]=2
            elif (row[1] in distbytree[row[0]]):
                row[3]=1
            else:
                row[3]=0
            cursor.updateRow(row)

# ---------------------------------------------------------------------------------
# Actually run script- YAY!

arcpy.MakeFeatureLayer_management(veg, "veg_layer")
forest = "veg_layer"
arcpy.env.workspace = scratch
arcpy.AddField_management(forest, "InRange", "LONG", 1)

# Create list of tuples that will define bin sizes
slicesorted = sorted(slices)
slicelist = zip(slicesorted, slicesorted[1:])


# Run near to get the distance and angle from each point to the tree
arcpy.Near_analysis(forest, seeds, "", "NO_LOCATION", "ANGLE")
# Convert that angle to azimuth. Otherwise would  be ridiculous with negatives.
with arcpy.da.UpdateCursor(forest, "NEAR_ANGLE") as angcursor:
    for r in angcursor:
        if r[0]<=180 and r[0]>90:
            r[0]=(360.0-(r[0]-90))
        else:
            r[0]=abs(r[0]-90)
        angcursor.updateRow(r)
del angcursor

arcpy.AddMessage("Starting iterations now")

slcount=0

##Create a list for values of all treeids and MBG_width, a list for treeids and MBG_length, list of treeids and length
average_pnt_distance=[]

for lo, hi in slicelist:
    slcount+=1
    whereclause = ''' "%s"<>-1 AND "%s"<%s AND "%s">%s'''%(treeid, HeightField, hi, HeightField, lo)
    arcpy.SelectLayerByAttribute_management(forest, "NEW_SELECTION", whereclause)

    LabelOutliers(forest, treeid)
    
    arcpy.SelectLayerByAttribute_management(forest, "REMOVE_FROM_SELECTION", '''"InRange"=1 OR "InRange"=2''')

    
    numstring = str(lo)
    if "." in numstring:
        numstring= numstring.replace(".","_")
    center_output_fc = "Center_%s" %numstring
    point_output_fc= "Slice_%s"%numstring

    ## Generate small selection of points
    slice_points=arcpy.FeatureClassToFeatureClass_conversion(forest, scratch, point_output_fc)

    ## Calculate Centerpoint of each
    center_points= arcpy.MeanCenter_stats(slice_points, center_output_fc, "", treeid)

    ## Run near from slice points to centerpoints
    arcpy.Near_analysis(slice_points, center_points)

    ## Add values to list of distances:
    tree_slice_distance=[]
    centerrows=arcpy.da.SearchCursor(slice_points, [treeid, "NEAR_DIST"])
    for pnt in centerrows:
        tree_slice_distance.append((pnt[0],pnt[1]))
    arcpy.AddMessage("Checking slice distances!")

    ## Average distances per tree
    treebyslice=defaultdict(list)
    for t, s in tree_slice_distance:
        treebyslice[t].append(s)
    for tree, slicelist in treebyslice.iteritems():
        average_pnt_distance.append((tree, mean(slicelist)))
        
    arcpy.AddMessage("Finished iteration number %s, slice %s"%(slcount, lo))

## create dictionary with values across
tree_mean_diameter=defaultdict(list)
for t, s in average_pnt_distance:
    tree_mean_diameter[t].append(s)
for tree, slicelist in tree_mean_diameter.iteritems():
    mean_radius=mean(slicelist)
    mean_diameter=mean_radius*2
    tree_mean_diameter[tree]=mean_diameter

    
arcpy.AddField_management(seeds, "Diameter", "DOUBLE", 4)

with arcpy.da.UpdateCursor(seeds, ["OBJECTID", "Diameter"]) as cursor:
    for row in cursor:
        row[1]=mean(tree_mean_diameter[row[0]])
        cursor.updateRow(row)














