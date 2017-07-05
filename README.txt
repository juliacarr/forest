---META---
Quick guide to going from point cloud to individual trees. This assumes a working knowledge of ArcGIS. At this point, the tools are built off ArcGIS, and the extensions 3D Analyst and Spatial Analyst. Make sure that these extensions are on when running the tools. 
We recommend to always look at your data between steps. The parameters may need to be adjusted for your specific dataset, and certain tests may be optimal with slightly different parameters. 


--- Instructions --- 
1. Generate point cloud from UAV imagery (Pix4D or Agisoft Photoscan recommended)
* High resolution LiDAR point clouds can be used as well. 
* Export as a .las file from your photogrammetric software. 

2. Bring into ArcGIS Desktop. Use the "Create LAS Dataset" tool in Arc (Data Management) to convert point cloud to .lasd that is usable in Arc. Generate statistics and apply coordinate system as necessary. 
* Tip: ArcGIS Pro and ArcScene are both recommended for seeing the point cloud in 3D and in color. 

3. Use ArcGIS’s “Classify LAS Ground” (3D Analyst). 
Recommendation: if the ground surface is unusually complex, may be best to mask certain areas (for example, we masked a small mine shaft collapse) and run with the ground classification on Standard first, then re-use those ground points and run as ‘Aggressive’ for the unmasked areas.

4.  Generate DEM. Filter the LAS to ground only, then use LAS Dataset to Raster (Conversion) tool to convert the ground to a raster. Set sampling value at roughly 4 times the point spacing. 

5. Convert LAS to Multipoint, and then separate with Multipart to Singlepart
* As of Arc 10.4, you have to navigate back to the original .las file, as the .lasd file is not an acceptable input. 
* RECOMMENDED: Filter only non-ground points from the LAS for faster processing time. This will cut the size of the feature class significantly.
6.  Extract Values to Points
* Here, you’re getting the elevation for each point based on the previously generated DEM. 
* arcpy.sa.ExtractValuesToPoints(singlepoint_fc, dem, output_fc)
8. Add fields for PointZ and PointHeight.  
* PointZ is the elevation of each point in the feature class. You can get these values by using the ‘Calculate Geometry’ tool in the table. 
* PointHeight is going to be the height of each point in the feature class. Use the Field Calculator to subtract the ground elevation (RASTERVALU from step 6) from the PointZ to get the height above ground for each point.
9. Run: IdentifySeedPoints
* Height field: the height from ground. 
* Slice boundaries: these are the boundaries you use for assessing the presence of points. Make sure to include both the bottom of the lowest slice, and the top of the tallest slice.
* Number of slices needed: This provides a bit of optional functionality—if you want to include 4 height classes, but only require that there is a presence in 3, could use this (use for clouds with inconsistent coverage) 
* 
10. Run: SegmentTrees
* Seed points: This tool should be run after the Identify Seed Points tool. You can substitute tree locations through manual identification, but recognize that the Tree ID will refer to the seed point’s object ID. 
* Distance for growth: This is the iterative growth distance. We RECOMMEND starting small (20 cm or so), and re-running the segmentation with a larger growth distance afterwards. That way, you can get the segmentation to correctly segment in the low, high point density, complex regions, and then increase for the sparse, low point density regions.
* Minimum height for growth: This is the height above which the point cloud is segmented. Since there often is low ground vegetation, noise in the ground classification, and other additional points below, this parameter allows you to start the segmentation above a certain height. Default value is 1m, which is recommended to be increased for complex ground surfaces, and decreased for flat, smooth ground.

* Add low: When checked, this adds the points below the minimum threshold height back into the final feature class. If not checked, those points stay in the scratch workspace.

* 
11: Run: MeasureDiameter
The output diameter is added as a field to the Seed Point feature class.
* Maximum Diameter Threshold: This represents the largest reasonable diameter for a tree in the site.  
* Angle threshold: The tool will calculate the average angle of each slice (that is, the most prominent angle from center away from the seed point), and use that to label points that are ‘angle outliers’—points that are likely to be a branch, or debris. The angle threshold is the searching distance from that average angle—here, by default




12. Add in ground trunks 
* After running the DBH tool, you can extrapolate the trunk into the unlabeled, low ground points. 
* 1) Run Buffer (Analysis) on the seed point feature class, using the DBH field as the buffer distance
* 2) select all unlabeled points (beneath the cut off threshold height) that fall within the buffers
* 3) Run NEAR, and label points with the NEAR id

Last updated by J. Carr on 6/7/2017


