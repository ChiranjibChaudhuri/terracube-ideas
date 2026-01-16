##### Contents lists available at ScienceDirect
ISPRS Journal of Photogrammetry and Remote Sensing
journal homepage: www.elsevier.com/locate/isprsjprs
```
An integrated environmental analytics system (IDEAS) based on a DGGS
```
Colin Robertson⁎, Chiranjib Chaudhuri, Majid Hojati, Steven A. Roberts
Department of Geography & Environmental Studies, Wilfrid Laurier University, Waterloo, Ontario, Canada
A R T I C L E I N F O
```
Keywords:
```
DGGS
Data model
Big data
Spatial data
Analytics
Environment
A B S T R A C T
```
Discrete global grid systems (DGGS) have been proposed as a data model for a digital earth framework. We
```
introduce a new data model and analytics system called IDEAS – integrated discrete environmental analysis
system to create an operational DGGS-based GIS which is suitable for large scale environmental modelling and
analysis. Our analysis demonstrates that DGGS-based GIS is feasible within a relational database environment
incorporating common data analytics tools. Common GIS operations implemented in our DGGS data model
outperformed the same operations computed using traditional geospatial data types. A case study into wildfire
modelling demonstrates the capability for data integration and supporting big data geospatial analytics. These
results indicate that DGGS data models have significant capability to solve some of the key outstanding problems
related to geospatial data analytics, providing a common representation upon which fast and scalable algorithms
can be built.
1. Introduction
It has been estimated that over 80% of data being produced today
```
are geospatial in nature (Hahmann and Burghardt, 2013). As the world
```
increasingly relies on data and algorithms to solve the most pressing
societal problems, new ways of processing, storing, integrating, ana-
```
lyzing and disseminating geospatial data are required (Gandomi and
```
```
Haider, 2015; Kitchin, 2014; Li et al., 2016; Guo et al., 2017). Many of
```
the initial technical advancements of the last two decades have been in
geospatial data acquisition: making significant advancements in earth
```
observation sensors (Ma et al., 2015), location sensing (Jendryke et al.,
```
```
2017), integration of virtual and physical content (Kamel Boulos et al.,
```
```
2017), and extracting geographic content from various forms of trans-
```
```
actional (Ma et al., 2013), user-generated (Ferrari et al., 2011) and
```
```
online content (Yasseri et al., 2013). These data sources represent a
```
significant opportunity to advance understanding across a wide variety
of disciplines. However, the development of appropriate analytical
approaches to this new data environment remains to some degree
fragmented and application-specific. In areas of image classification for
example, convolutional neural network models have made huge strides
in recognizing and predicting objects and scenes in geospatial data,
```
which are increasingly being deployed in earth observation (Hu et al.,
```
```
2015), unmanned aerial vehicle (Gruszczyński et al., 2019), and lidar
```
```
data applications (Guan et al., 2015). In this case, data are assumed to
```
be aligned over a multidimensional pixel array, some with known class
labels, which are used to train the model. This analytical setting – while
common to image geodata – is still only a small proportion of all big
geospatial data. New analytics for line object data, or geospatial time
series, or trajectory data are all needed. More critically, next-generation
geospatial data models are required to realize the potential benefits of
geospatial big data by incorporating data from different sources and
```
representations. Discrete Global Grid Systems (DGGS) have been pro-
```
posed as one way to bring disparate geospatial data together into a
common spatial fabric that provides a basis for unified analytics. In this
paper we aim to explore this idea through the investigation of four
```
research objectives;
```
1. Create an operational DGGS-based GIS which is suitable for en-
vironmental modelling and analysis in a big data platform.
2. Evaluate DGGS implementations of common GIS algorithms.
3. Demonstrate analytical capability of a DGGS-based GIS for en-
vironmental analysis and modelling
4. Develop a browser-based UI that allows users to interact and run
algorithms on the data stored on the centralized server or decen-
tralized storage.
```
Discrete Global Grid Systems (DGGS) are gaining traction as a data
```
model for a digital earth framework that is designed for heterogeneous
```
geospatial big data (Craglia et al., 2008, 2012a; Goodchild, 2018;
```
```
Goodchild et al., 2012). While the fields of remote sensing and
```
GIScience have pushed geographic information technologies further
```
into the big data era (Miller and Goodchild, 2015), most approaches to
```
```
https://doi.org/10.1016/j.isprsjprs.2020.02.009
```
```
Received 4 October 2019; Received in revised form 24 January 2020; Accepted 13 February 2020
```
⁎ Corresponding author.
```
E-mail address: crobertson@wlu.ca (C. Robertson).
```
```
ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
```
Available online 09 March 2020
```
0924-2716/ © 2020 The Authors. Published by Elsevier B.V. on behalf of International Society for Photogrammetry and Remote Sensing, Inc. (ISPRS). This is an
```
```
open access article under the CC BY license (http://creativecommons.org/licenses/BY/4.0/).
```
T
handling and managing spatial data within GIS still rely on computa-
tional implementations of concepts and ideas that were designed for
```
paper maps (Li et al., 2016). Map projections have been implemented in
```
```
widely-used libraries such as proj4 (PROJ contributors, 2019), however
```
when data are natively digital from the time of acquisition to the time
that data are used in some decision-making context on a mobile app or
```
digital globe; it is unclear whether projecting to planar coordinates is
```
```
still required (Goodchild, 2018). Further, many other branches of
```
standard geospatial data analysis and management facilitated by
modern GIS software replicate non-digital ways of interacting with
geographic information. There is renewed interest in developing a
completely digital geospatial pipeline with support for real time data.
DGGS are emerging as a potential data model for supporting this
```
computational infrastructure (Craglia et al., 2008, 2012b; Mahdavi-
```
```
Amiri et al., 2015).
```
Specific criteria for what constitutes a DGGS have evolved over the
```
years from Goodchild’s criteria (Goodchild, 1994), which was extended
```
```
by Kimerling et al. (1999) and recently codified into the abstract OGC
```
```
specification (Purss et al., 2017a, 2017b). In short – a DGGS is a system
```
of hierarchical grids where each grid tessellates the earth with equal-
area cells at a specific resolution. Generally speaking, the tessellation is
performed on a base geometry that approximates the globe and is
```
projected to the datum surface. Foundational work by Sahr et al. (2003)
```
showed that base geometric model used for a DGGS can be one of the
five platonic solids if minimizing cell area differences is a goal. Direct
```
coordinate referencing on the sphere (e.g., latitude and longitude)
```
produce significant variations in cell size and shape in different regions
which makes many geometric and spatial analysis algorithms difficult.
As a result, the modern spatial analysis workflow still involves con-
verting three-dimensional spherical coordinates to planar coordinates
before analysis is performed. Base platonic solids used to model the
earth are the tetrahedron, hexahedron, octahedron, dodecahedron, and
```
icosahedron (Sahr et al., 2003), and in terms of minimizing inter-cell
```
```
variability; the icosahedron has been found to outperform other shapes
```
```
(Gregory et al., 2008). The tessellation of projected solid faces on the
```
sphere can use different shapes, such as squares, triangles, or hexagons.
The choice of cell geometry has significant implications on algorithm
and index development for these systems.
```
Examples of modern DGGS frameworks included healPix (Górski
```
```
et al., 2018), openEager (Bush, 2016), Uber’s H3 (https://eng.uber.
```
```
com/h3/), rHEALPix developed by landcare (Gibb et al., 2016),
```
```
DGGRID (Sahr, 2018), among others. While these systems are in active
```
```
development and may not yet fully conform to OGC criteria (Bondaruk
```
```
et al., 2019), core functionality common to these frameworks include
```
cell addressing functions, conversion to and from geographic co-
ordinates, and having cells defined as simple convex geometries that
completely tessellate the earth. More sophisticated criteria such as
spatial analysis algorithms, data quantization, broadcasting, and query
and neighborhood functions are less widely developed. There remains
significant work to be done in moving DGGS forward to function as part
of an operational GIS capable of meeting the goals of the digital earth
```
vision (Craglia et al., 2008, 2012b) and the challenges of big geospatial
```
data analysis. For example, a considerable degree of processing of
geospatial data is typically required as preprocessing before data can be
```
utilized (Comber and Wulder, 2019; Appel and Pebesma, 2019) and
```
```
without standard processing tools for DGGS (e.g., SQL), nor interoper-
```
```
ability standards between DGGS implementations (Amiri et al., 2015),
```
data processing requirements are currently very high.
While DGGS are by definition global in scope, and are in part de-
```
veloped to support digital earth applications that have a global domain;
```
many analysis contexts require global data to be fused with regional
and/or local observations. Often the decision-making context is at most
```
national in scale (if not regional or local), yet required geospatial data
```
are obtained from satellite sensors, mapping projects or citizen-science
```
initiatives such as OpenStreetMap; or Wikimapia - which are global in
```
```
scope. Resources to build these systems also tend to be localized;
```
focusing on specific regions and problem domains: global data inputs
are required to understand, describe, and predict local phenomena.
Even when spatial query access is supported by API access to global
datasets, integrating data in terms of spatial scale, measurement units,
temporal scale, and semantics is a major constraint to seamless big
```
(geo) data analysis (Wang and Yuan, 2014). One of the more promising
```
aspects of DGGS data models for handling big spatial data is the po-
```
tential to solve this data integration problem (Purss et al., 2017a,
```
```
2017b; Goodchild, 2018).
```
1.1. From continuous to discrete space
A fundamental characteristic of a DGGS data model is that geo-
graphic data are stored in discrete cells rather than as coordinates in a
```
continuous underlying space. Goodchild (2018) has conceptualized
```
DGGS as a form of ‘congruent geography’, similar to raster or planar
vector models, but distinct in the use of hierarchical tessellations to
accommodate different scales/levels of spatial uncertainty. According
```
to Goodchild (2018), the advantages of DGGS representations for ex-
```
plicitly incorporating spatial measurement uncertainty, data integra-
tion, and analytics outweigh the mostly cartographic drawbacks to a
discrete representation based on a DGGS. As well, some of the classical
challenges for GIS processing of complex variations of geographic ob-
jects or fields such as hierarchies of nested objects and the statistical
analyses of spatial variation may be reduced through a DGGS data
model.
Discrete space representations have the advantage of avoiding the
theoretical and practical problems of using finite state machines
```
(computers) to represent non-finite objects. Specifically, working with
```
integer values for distance and location measures avoids the theoretical
and practical complications of computing with floating point numbers
```
(the common computational model of real numbers). Computation is
```
faster and more predictable in terms of working in a completely en-
umerated discrete space. To emphasize this point, the space is also
mathematically complete in that operations such as intersection are
guaranteed to have a solution in the discrete space. This is not the case
when assuming, for example, an underlying Euclidean plane numeri-
cally modelled with floating point representations. Further, the topo-
logical problems that arise when using a discrete space to model a
continuous space can be largely avoided. In particular, using hexagonal
```
cells avoids topological ambiguity in neighbourhood definition (e.g.,
```
```
Rooks' vs. Queens' neighbourhoods) and sidesteps, due to the homo-
```
```
geneity of boundary type (all edges for hexagon tessellations), other
```
instances like Jordon's curve theorem and Helly's theorem of convex
partitions where a continuous spaces' topological properties fail when
```
that space is discretized (Webster, 2003; Schneider, 2000; Hales, 2007).
```
1.2. Big spatial data analytics approaches
There have been several proposals and developments for big data
GIS in recent years which aim to facilitate the management, storage,
```
analysis, and processing of big data (Jo and Lee, 2018; Mahdavi-Amiri,
```
```
Alderson, and Samavati, 2015). The computing architecture for big
```
geospatial data has evolved with computing trends generally over re-
cent years, and now encompasses a mix of architectures including
Cloud GIS, IoT GIS and other types of service-oriented architecture
```
(Alesheikh and Helai, 2002; Bhat et al., 2011; Cao and Wachowicz,
```
```
2019). In this architecture, the complexities of the analytics stay behind
```
a centralized server and the user interacts with the server via an easy-
to-use web-based browser interface. This architecture requires the de-
velopment of a user-friendly and comprehensive operational library
```
that supports interactive data analysis (as opposed to simple visuali-
```
```
zation of precomputed analyses). Despite many different flavours of
```
service oriented architecture for big geospatial data analytics, chal-
lenges remain to implement a coherent, robust, and scalable analytics
```
system (Gao and Goochild, 2013).
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
215
```
Data cubes and spatio-temporal databases (e.g. GeoMesa or
```
```
MobilityDB) are recent incarnations that simultaneously support the
```
storage and analysis of both time and spatial dimensions of data. A data
cube is a multidimensional array of data coupled with a set of metadata
```
describing coordinates, values and cell data (Han et al., 2012; Purss
```
```
et al., 2019). The beginning of the use of data cube terminology goes
```
back to the implementation of data mart, dashboards and data ware-
```
house architecture (Nativi et al., 2017; Purss et al., 2019). Data cubes
```
facilitate multidimensional data processing and are used in big earth
```
data platforms such as Open Data Cube (ODC) by CEOS (Giuliani et al.,
```
```
2017) and EarthServer by EU (Baumann et al., 2016) as well as fre-
```
quently employed for hyperspectral data representation and analysis
```
(Nativi et al., 2017). Online analytical processing (OLAP) data cubes
```
```
and spatial variants (e.g., SOLAP by Li et al. (2014)) require pre-com-
```
puting aggregate and join operations and thereby rapidly increase
query speeds.
MapReduce-based data models and platforms are mainly key-value
data models which are widely used for parallel and distributed big geo-
```
data computations (White, 2012). Hadoop is based on a MapReduce
```
```
architecture but its core does not support spatial data (Jo and Lee,
```
```
2018) and for this reason a set of spatial enabling extensions have been
```
```
developed to add spatial data handling support to these platforms; such
```
```
as ESRI GIS tools (Esri, 2019), Hadoop-GIS (Aji et al., 2013), GPHadoop
```
```
(Gao et al., 2017) and SpatialHadoop (Eldawy, 2014). Many of these
```
platforms are restricted by Hadoop limitations itself and the integration
of the spatial and regular system functions have been shown to have
```
degraded performance (Jo and Lee, 2018). Other platforms such as
```
BigQuery support native GIS functions, however in this case there is a
maximum of 2000 features per map and it only supports geometry in-
puts in WKT format stored in a string column. Some other platforms
```
such as LandQ (Yao et al., 2018) use the GeoCSV data type which has a
```
key-value data format, employing OGC-WKT as the spatial dimension.
GeoMesa is spatio-temporal NoSQL database launched by the Federal
Computer Research Center that enables large-scale geospatial analytics
```
on distributed computing systems (Hughes et al., 2015), employing a
```
key-value structure where each row is stored and fetched using a un-
ique identifier for that record. The main feature of the GeoMesa index is
a representation of three dimensions of longitude, latitude, and time
```
with a three-dimensional space-filling curve (Commonwealth Computer
```
```
Research Inc. 2019).
```
The platforms discussed above either build on the spatial data
```
model expressed in OGC-WKT; or implement specific realizations of
```
field and object data models. As such, data modelling capabilities are
somewhat restricted and the capability to natively incorporate hetero-
geneous spatial data is limited. Given the data integration potential for
DGGS-based data models to support big geospatial data architectures
and the importance of integration in the big geospatial data era
```
(Goodchild, 2018), we developed a DGGS-based GIS for environmental
```
modelling and analysis called the Integrated Discrete Environmental
```
Analysis System (IDEAS). Here we report on the system’s architecture,
```
temporal data model, spatial data model, user interaction, visualiza-
tion, and implementation of several common GIS algorithms. We de-
monstrate our system through a case study which highlight its analy-
tical and dynamic modelling capabilities.
2. Methods
2.1. Description of IDEAS
The following subsections describe the overall IDEAS system model
and in turn its component spatial, temporal and attribute data models
along with the supporting metadata model and auxiliary data.
2.1.1. IDEAS-data model
The IDEAS is a DGGS-based platform for analysis of big geospatial
datasets. Here we briefly review the architecture, design decisions, and
conceptual schema of IDEAS. GIS data have historically been char-
```
acterized by three information dimensions; the spatial dimension, the
```
```
temporal dimension, and the attribute (i.e., thematic) dimension(s)
```
```
(Sinton, 1978). We use this idea to delineate three core sub-models of
```
```
IDEAS; the spatial data model, the temporal data model, and the at-
```
tribute data model.
The IDEAS data model is based on a hybrid relational/key-value
database model. The atomic unit of IDEAS is a cell-object which re-
presents a single characteristic of one cell in the DGGS representing one
area of the earth’s surface over a specified duration of time. This design
consideration was selected to achieve maximum flexibility and ac-
commodate variable-extents and schemas in input data. Each cell-object
```
has three main dimensions: (i) spatial dimension (the area of the earth
```
```
it covers, stored as an integer), (ii) temporal dimension (the duration of
```
```
time the measurement pertains to, stored as an integer) and (iii) attri-
```
```
bute dimension (the thematic characteristic being represented, stored
```
```
as a key/value pair). In this data model, each row is a 5-tuple of values
```
```
including dggid (spatial identifier), tid (temporal identifier), key (at-
```
```
tribute identifier), value and dataset (metadata identifier). The resolu-
```
tion of each cell-object is determined explicitly in both space and time
and intended to be matched to the measurement scale of the data ac-
quisition process. Each attribute is stored as a key/value pair for each
```
cell-object. At any given time, each cell can have several attributes (i.e.,
```
```
cell-objects) which describe features (e.g., temperature, land cover, soil
```
```
moisture) of the cell at prescribed times. To separate different datasets
```
and attach metadata another column named dataset is added into the
tuple which has a many-to-one relation with an external metadata
table. This 5-tuple cell-object schema is stored as a single long table in a
relational database. With this structure, adding, editing, or deleting
new attributes is easily handled while avoiding difficulties of querying
present in no-SQL databases. As well, this data model can be im-
plemented on big data platforms that favour long tables over traditional
database normalization. Realizations of higher level data model con-
```
cepts (e.g., complex spatial objects, topologies, etc.) can be im-
```
```
plemented as functions over this single schema; a significant advantage
```
over standard relational schema common in GIS.
2.1.2. spatial data model
```
DGGS are defined by several design parameters: (1) the base regular
```
```
polyhedron, (2) the shape of cells and the subdivision method, (3) the
```
```
orientation of the polyhedron on the selected earth model and, (4) the
```
method to project the cells from a planar surface to the selected earth
```
model (Sahr et al., 2003).
```
The regular icosahedron has the smallest face size which results into
relatively small distortions of the DGGS cells that are based on it
```
(Fig. 1a) (Gregory et al., 2008; Sahr et al., 2003). A few examples of
```
```
such DGGS are; Williamson (1968), Sadourny et al. (1968),
```
```
Baumgardner and Frederickson (1985), Sahr and White (1998), White
```
```
et al. (1998), Fekete and Treinish (1990), Thuburn (1997), White
```
```
(2000), and Song et al. (2002). The subdivision of the DGGS cells in-
```
volves the choice of the shape and partitioning strategy. There are 4
```
types of shapes that are common for partitioning; triangles (Kenner,
```
```
1976) (Fig. 1b), diamonds (White, 2000) (Fig. 1c), hexagons (Kimerling
```
```
et al., 1999) (Fig. 1d), and squares (Alborzi and Samet, 2000) (Fig. 1e).
```
Hexagons are the most compact, they quantize the plane with the
```
smallest average error (Conway and Sloane, 1998), and they provide
```
```
the greatest angular resolution (Golay, 1969) among all the regular
```
polygons that tile the plane. However, it is impossible to completely tile
a sphere with a hexagon-based tessellation. The hexagon-subdivided
triangles form a non-hexagon polygon at each of the polyhedron ver-
```
tices (i.e., pentagons). The number of pentagons in such a system will
```
remain constant regardless of the resolution of the grid. In the case of an
icosahedron base geometry there are 12 pentagons. True hexagonal
DGGS algorithms must be designed to accommodate pentagons to
support global scale processing.
One limitation of hexagon tiling is that larger hexagons cannot be
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
216
decomposed evenly into smaller hexagons to form a clear packing
```
hierarchy (the way squares can). White et al. (1992) proposed hexagon
```
```
grids of aperture 3 (Fig. 1f), 4 (Fig. 1g), or 7 (Fig. 1h), and White et al.
```
```
(1998) discussed hexagon grids of aperture 4 (Class I) and 9 (Class II).
```
```
Sadourny et al. (1968) used a Class I hexagon grid of arbitrary aperture,
```
which is incongruent and unaligned. We selected an aperture 3 hexagon
hierarchy due to the relatively simple nesting of thirds for neighbouring
resolution hexagon geometries.
The most straightforward choice of the orientation of the poly-
hedron compared to the underlying earth model would be to place a
vertex at each of the poles and then align one of the edges originating
```
from the vertex at the north pole with the prime meridian (Williamson,
```
1968, Sadourny et al., 1968, Fekete and Treinish, 1990, and Thuburn,
```
1997) (Fig. 1i). Fuller (1975) placed the one vertex of the polyhedron
```
on at 5.24° W longitude, 2.30° N latitude and a second one at an azi-
muth of 7.46° from the first vertex. This created an orientation where
all the 12 icosahedron vertices fall in the ocean so that the icosahedron
can be unfolded onto the plane without any deformation in the land
```
areas. Sahr et al. (2003) placed one vertex at 11.25° E longitude, 58.28°
```
N latitude and an adjacent one at an azimuth of 0.0° from the first
vertex which created an orientation of the polyhedron where all but one
vertex falls on the ocean and is also symmetric about the equator
```
(Fig. 1j). However, there are certain orientations found in the literature
```
which considers a specific continent in mind while orienting the base
```
polyhedron (White et al., 1992). The orientation of the IDEAS base
```
```
polyhedron is defined such that all of Canada (the focal region for our
```
```
analysis) fits within one DGGS quadrilateral. Here, the north pole is
```
```
placed on 178°W and 37° N (Fig. 1k).
```
The sub-divided polyhedron must be projected onto the spherical or
ellipsoidal surface. The subdivisions can be categorized into two ap-
```
proaches (Kimerling et al., 1999): 1. direct spherical subdivision ap-
```
```
proaches and 2. map projection approaches. White et al. (1998) discuss
```
the area and shape distortions of subdivisions. According to the OGC’s
specifications the DGGS cells should have an equal area. Therefore, we
```
used an Icosahedral Snyder Equal Area (ISEA) map projection in our
```
system. Therefore, the DGGS used for IDEAS is an icosahedral Snyder
```
equal area aperture 3 hexagon (ISEA3H) DGGS (Sahr et al., 2003).
```
Depending on the requirement of the analysis algorithm the system
uses different types of addressing schemes. For pyramid type addressing
```
we used Quadrilateral 2-Dimensional Integer (Q2DI) indexing (Sahr,
```
```
2008). The orientation of the hexagon grids alternate in successive re-
```
```
solutions between Class I (Fig. 2a) and Class II (Fig. 2b) in aperture 3
```
hexagons. The class I axis is used for odd-resolution and class II axis is
```
used for even-resolution grids (Sahr, 2008). However, Class II grids do
```
```
Fig. 1. (a) Icosahedron faces projected onto a sphere (b) Triangular tessellation (c) Diamond tessellation, (d) Hexagonal tessellation, (e) Square tessellation, (f)
```
```
Aperture 3 grid, (g) Aperture 4 grid, (h) Aperture 7 grid, (i) Projected Icosahedron faces oriented with poles at the 90° N Latitude and 0° Longitude, (j) Projected
```
```
Icosahedron faces orientated with poles at the 58.28° N Latitude and 11.25° W Longitude, (k) Projected Icosahedron faces oriented with poles at the 37° N Latitude
```
and 137° W Longitude.
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
217
not align with the Class I coordinate axes which is defined by the
```
quadrilateral edges. Sahr (2008) proposed a solution to this problem by
```
assigning each Class II resolution k cell the coordinates of the Class I
```
resolution k + 1 cell centered upon it (Fig. 2c). For a 1-dimensional
```
```
referencing scheme, the Space Filling Curve (SFC) (Fig. 2d) (Gotsman
```
```
and Lindenbaum, 1996, Psomadaki et al., 2016) implemented by Dis-
```
```
crete Global Grids Software (Barnes, 2016) was used to generate unique
```
```
Discrete Global Grid Identifiers (DGGID). Most of our algorithms were
```
constructed based on this DGGID. However, some algorithms such as
neighborhood or parent–child identification use the Q2DI indexing
system. Parent-child relationship finding is a key need for many GIS
operations and analyses such as aggregation. The linkage between the
central cells at any resolution can be tracked in the Q2DI system. For
any resolution r 1 a Q2DI central cell location vector Vr1 corresponds to
an appropriately scaled resolution r 2 central cell location vector“ r2r1 as
```
follows (Sahr, 2008):
```
4 ×
×
V for resolution r and r of same class
V otherwise
3 ,
3 , .
r
r
1 2 1
1
r r
r r
```
( 2 1)2
```
```
( 2 1 1)2(1)
```
Neighbourhood identification is an equally important task for many
algorithms and analyses. For a given distance D cells in the DGGS can
```
be tracked in the IJ-indexing system (Fig. 2). Any given’ ffi( , )b b which is
```
```
at a distance9 cells away from’ ffi( , )a a , satisfies the formula;
```
```
4 p p pD abs I I abs J J abs I J I J( ) ( ) ( )2a b a b a a b b(2)
```
Since the study region of IDEAS falls within a single quadrilateral q,
our neighbour-finding methods do not currently handle neighbour-
hoods crossing quadrilateral boundaries. We aim to extend this func-
tionality in future revisions.
2.1.3. Temporal data model
GIS-based analysis typically incorporates time representation in two
```
different ways, (i) by considering different points in time as a means to
```
```
detect historical changes (i.e., the so-called ‘snapshot model’), and (ii)
```
by abstracting the time dimension of change into periods or stages. We
propose an indexing method for time which we store for each cell-ob-
ject. Similar to the spatial context, temporal uncertainty can be better
represented by durations than single points in time. Though we con-
ceptualize our measurement representation over a discrete instance of
space–time at the cell-object level, we need to store representations in
the spatial and temporal domain separately due to the combinatorial
increase in integers required for possible realizations of space–time. As
such, a discrete method for indexing time was implemented according
to typical temporal scales needed in GIS-based environmental
```
Fig. 2. Indexing methods in DGGS. (a) Class I grid, (b) Class II grid, (c) Mapping of Class II to Class I grid, and (d) Space Filling Curve.
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
218
monitoring and analysis. We propose an ordinal temporal schema for
indexing of temporal durations based on fixed start and end points.
Although infinite durations are possible, a subset of commonly used
durations were implemented. The definition of the study period and the
duration subset is a temporal analogy to the selection of the spatial
extent and cell geometry in the spatial domain.
```
The temporal data model was constructed to be multi-resolution (to
```
```
allow for different durations of discrete size) and hierarchical (to sup-
```
```
port duration nesting). Suppose the beginning of the time period is t1
```
and the end of the time period is t2. Then the whole time duration
between t1 and t2 is separated into different levels such as 1000 years,
500 years, 100 years, 50 years, 1 year, 12 months, 7 days, 1 day, 1 h,
```
1 min and 1 s. This hierarchical structure (Fig. 3) defines the time re-
```
```
solution of each cell-object. The time index (TID) is an integer value
```
which starts from 0 and for each resolution the count of each division is
added to previous number of divisions in previous time resolution. As
the value of the time index increases the resolution of time also in-
```
creases (i.e., the size of the duration decreases). Table 1 shows the
```
number of divisions in each time resolution for 2000 years. The discrete
nature of temporal definition developed for IDEAS allowed us to easily
distribute the data for parallelization. Using this model both geo-
graphical time models are supported. One of the limitations of this
proposed time structure is its definition is based on fixed intervals. The
definition of a time projection structure might be considered to account
for discrepancies between the models with varying respective time
limits.
2.1.4. Attribute data model
The information characterizing each cell-object is stored as key/
value pairs. These pairs can include what are typically modelled as
attributes in GIS, as well as topological and measurement information.
The keys are mapped to a corresponding key-value attribute metadata
table which provides semantic interpretations of keys in the base table.
2.1.5. Metadata model
A metadata model is used to provide interpretation of keys, in-
corporate dataset-level information, and facilitate computations and
algorithms employing data in the base table. The minimum required
information for a metadata record is as follows:
1. Extent: This field is saved in the form of minimum and maximum
values of a dataset’s boundary box coordinates. This parameter is
mainly used for visualization purposes and initial checks for some of
the algorithms.
2. Dataset Name: In the proposed data platform each dataset is stored
with a dataset name. This name is unique and is used to attach
metadata to each dataset.
3. Minimum/Maximum Zoom level: These two fields are used for
data visualization. Each dataset can have a minimum and maximum
zoom level to be used by client map libraries to only show the da-
taset between minimum and maximum zoom levels.
4. Minimum/Maximum Value: In order to visualize continuous data
```
(e.g. temperature and other types of data that comes in continuous
```
```
raster data format) the map rendering engine needs to know about
```
minimum and maximum value of each band.
In addition to these four fields, we have optional fields for de-
scriptive details such as lineage, contact information, source, etc. As
well, the DGGS resolution can be stored as metadata. This parameter is
used for visualization, aggregation between resolutions, and some of
the DGGS base functions such as finding neighbors, drawing lines be-
tween two sets of DGGS ids and so on.
2.1.6. Auxiliary information
In order to implement a realization of common spatial data types
and objects from the IDEAS data model, we can implement specific
```
attributes (i.e., key/value pairs) that operationalize aspects of topology
```
```
or geometry (i.e., sets of cells) with spatial semantics required for
```
common types of GIS analysis. We designate these ‘special attributes’ as
auxiliary information, noting that these are simply examples of ag-
gregates and functions on our base data model - not part of the data
Fig. 3. Time pyramid index system. Each row represents a different resolution for the entire time period. Indexing starts from the courser resolution and adds up to
finer resolutions.
Table 1
Temporal lookup table for time data model. Time resolution values are valid for
durations during study period defined from 1000-01-01 to 3000-01-01.
TLUID Resolution TID Start TID End
1 1000 Years 1 2
2 500 Years 3 6
3 100 Years 7 26
4 50 Years 27 66
5 10 Years 67 266
6 1 Year 267 2266
7 Month 2267 26,266
```
8 Week(7 Days) 26,267 120,621
```
9 Day 130,622 861,106
10 Hour 861,107 18,392,746
11 Minute 18,392,747 1,070,291,150
12 Second 1,070,291,151 64,184,195,388
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
219
```
model itself (Table 2). Application-specific iterations of key/value pairs
```
can be implemented to achieve representation of complex spatial ob-
jects.
2.2. IDEAS data processing
There are an increasing number of sources available for acquiring
spatial data, so importing existing data into our DGGS data model is a
key data processing requirement. The quantization of spatial data into
the IDEAS system is done through uniform spatial sampling at the DGGS
resolution selected to match the spatial uncertainty in the input data.
For instance, for converting raster data into a DGGS grid, the raster’s
resolution is used to select the nearest DGGS cell resolution. For vector
data, the positional accuracy of input data is used to find the best DGGS
resolution. It worth noting that in the current implementation of the
system multiresolution representations are not explicitly stored, but can
be computed through aggregation as needed. For spatial point data,
after determining the target resolution, the point’s geographic co-
ordinates are converted to a corresponding DGGID. For raster data, the
bounding box is used to extract a set of DGGS cells, and then for each
```
DGGS cell’s centroid the raster value is extracted (Fig. 4a). Standard
```
approaches for values resampling can be used to to extract values for
each DGGS cell based on nature of data and application, for instance for
a parameter such as temperature a mean value of underlying raster cells
can be used, or for categorical data nearest neighbor resampling is more
suitable. To convert polygon data to a DGGS data model, we sample
from its interior and its boundary separately using uniform sampling.
The sampling distance is determined as one unit higher than the target
DGGS cell’s resolution cell centroid distance to ensure that the resulting
DGGS cells will cover the entire area of the polygon without gaps.
Vertices of the boundary are extracted and sampled along line segments
at the specified sampling distance. Then each sample point is converted
into DGGS cells based on its coordinates and stored into IDEAS data
```
model by aggregating both sets of DGGS cells (Fig. 4b). In the ag-
```
gregation step duplicate DGGS cells are also removed and boundary
cells are coded with an auxiliary attribute. The same process for the
border extraction is applied to the polylines and networks, however
with network data the order of the cells is also stored as a flag to use in
```
directional analysis (Fig. 4c).
```
2.3. - IDEAS architecture
The DGGS data model described above was implemented as tables
in a relational database. Each cell in the spatial data structure is as-
signed a unique DGG-ID value that is derived from a one-dimensional
space-filling curve. The DGG-ID is the primary organizing key for the
entire data structure - which, due to the size of the spatial fields at
```
higher resolution, must be stored as a 64-bit integer (w/valid values
```
```
range of −(2 64 /2) to (264/2 − 1)).
```
Fig. 5 illustrates the table structure of the IDEAS data model. It
consists of five main tables: Base, Attribute, Temporal Lookup, Geo-
metry, and Metadata. The base table is the main table in which all the
cell-objects and their values are stored. As noted above, TID is used to
represent the time duration for each cell-object. TID is an integer
column whose values can be resolved to a specific duration in the study
period through its relation to the temporal lookup table. While the
exhaustive list of TIDs are not stored explicitly, the full list of DGG-ID
values are stored in the Geometry table. For the purpose of doing some
analysis such as moving window analysis the two-dimensional I and J
```
indexes (Q2DI) are needed. Also, for the purpose of data visualization
```
since a hexagonal cell map rendering engine does not presently exist the
geometry of each cell is also stored in the Geometry table. The database
is implemented in a Netezza data warehouse appliance with 40 nodes
and makes use of programmable field gate arrays to optimize query
speeds. As a database appliance, indexes and tuning requirements are
kept to a minimum and analytics and a wide variety of analytics al-
```
gorithms are available for incorporating into IDEAS (Francisco, 2011).
```
However, the underlying schema and architecture of IDEAS could be
employed on other relational data warehousing and/or cloud-based
systems.
2.4. User interaction
Users can interact with IDEAS through several interfaces. The pri-
```
mary method to interact with the database is via an R client (Ihaka and
```
```
Gentelman, 1996; R Core Team, 2018). R has become one of the leading
```
data analytics platforms due to its wide array of user-contributed
packages, free and open source codebase, and specialized collections of
```
packages which interoperate (e.g., spatial packages, the tidyverse
```
```
packages, etc.). We deploy the R package dbplyr (Wickham and
```
```
Francois, 2016) which provides database access within a grammar of
```
analytics and data processing offered through the tidyverse group of
```
packages (Wickham, 2017). As noted by Baumer (2019), the dbplyr
```
significantly increases the capability of users to do ‘in-database’ ana-
lytics without having to learn or refactor regular R code into SQL. In our
case, the dbplyr package allows us to write algorithms for operating on
IDEAS data using R. Furthermore, its lazy execution feature enabled us
to run all queries in one execution to retrieve final results. Since R is a
widely known data analytics language, all that is required is for users to
gain some familiarity with the IDEAS data models in order to develop
their functions and analytic processing chains.
The second key way we interact with IDEAS data is through the
```
deployment of web applications using the R/Shiny framework (R
```
```
Development Core Team, 2018). R/Shiny provides rapid web applica-
```
tion development tools within the R environment. User interfaces can
be created by binding UI controls to data, analysis functions, and gra-
phics that support user interaction with data. The robustness and easy
integration of R/Shiny with the R-programming language, and the ease
of use of the R/Shiny UI enabled us to use this as a basis for application
development for IDEAS instead of depending on any specific visuali-
zation platform or dashboard. For example, one basic visualization
system we developed with R/Shiny uses a Leaflet mapping control and
webGL representation of vector geometries stored in the database
```
(https://github.com/r-spatial/leafgl). As well, this architecture ensures
```
memory limitations of R are minimized when working with big geos-
patial datasets. Numerous graphing and visualization options are
available using R and R/Shiny which facilitate interactive big data
analysis. The entire analysis, user interaction, and visualization system
```
is developed to serve as a standalone GIS analytics platform (Fig. 6).
```
Table 2
Auxiliary attributes for coding common spatial object types as attributes in the IDEAS data model.
Auxiliary Attribute Description
Order For line and network data types in process of converting line to the list of DGG cells the order of the cells also are stored. This order is an integer value which
starts from 0 to N and shows the line direction
Boundary This is a boolean data field which is used in the process of converting polygon data into a DGGS data model. The set of DGG cells which are on the border of
polygon feature get the boundary key equal to 1 and the other interior cells get a value of 0. This attribute can be used for some of the spatial analysis such as
buffer.
Band This key is mainly used for the raster data which stores the data for each band in a raster data
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
220
2.5. GIS functionality
2.5.1. GIS operations overview
Geospatial analysis consists of many different analytical approaches
which originate from the various disciplines which have contributed to
it over the years. For a spatial data model to be effective and robust, it
must be able to handle different analysis procedures such as, geometric
operations, spatial statistics, map algebra, and network analysis. In this
```
Fig. 4. Data conversation flowchart (a) Raster data (b) Vector Data (Point, Line, Polygon), (c) Network.
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
221
section, we demonstrate the implementation of some commonly used
spatial and geometric operations in the context of the DGGS-based
spatial data model. For illustration purposes, we assume a table called
RASTER and a table called POLYGON which we use to illustrate some
key GIS operations using our DGGS-based GIS. The dbplyr snippets of
different raster and vector operations are presented in the following
section.
Map algebra: The implementation of any mathematical function on
a base raster grid is referred to, in general, as map algebra. Based on its
```
spatial scope, map algebra operations can be divided into 4 categories;
```
```
local (functions operate on each cell independently) (Fig. 7a), focal
```
```
(functions operate on a neighbourhood around each cell) (Fig. 7b),
```
```
zonal (functions operate on an arbitrarily defined neighbourhood)
```
```
(Fig. 7c), and global (functions operate on all cells) (Fig. 7d) functions.
```
The crucial step in the DGGS context is identifying the cells in focal
neighbourhoods.
##############LOCAL################################
```
RASTER=tbl(con,“RASTER”)
```
```
LOCAL_1=mutate(RASTER,LOCAL_1=VALUE+5)%>%show_-
```
```
query()
```
```
LOCAL_2=mutate(RASTER,LOCAL_2=VALUE+LOCAL1)
```
##############FOCAL_MEAN###########################
```
POLYGON=tbl(con,“POLYGON”)
```
```
NEIGHBOR=tbl(con,“NEIGHBOR”)
```
```
JOIN=POLYGON%>%inner_join(.,NEIGHBOR,by=c
```
```
(“DGGID”=“DGGID”))
```
```
JOIN=JOIN%>%group_by(DGGID.x)%>%summarise(mean=-
```
```
mean(VALUE.x,na.rm = TRUE))
```
##############ZONAL
MEAN###########################
```
RASTER=tbl(con,“RASTER”)
```
```
POLYGON=tbl(con,“POLYGON”)
```
```
RASTER_P=RASTER%>%inner_join
```
```
(.,POLYGON,by=“DGGID”)
```
```
ZONAL_MEAN=RASTER_P%>%group_by(VALUE.y)%>%sum-
```
```
marise(mean=mean(VALUE.x,na.rm = TRUE))
```
##############GLOBAL_SPATIAL_COVARIANCE#############
```
RASTER=tbl(con,“RASTER”)
```
```
GRID=tbl(con,“GRIDLOOKUP”)
```
```
GRID=select(grid,DGGID,I,J)
```
```
RASTER=RASTER%>%inner_join(.,GRID,by=“DGGID”)
```
```
RASTER=mutate(flood,K=-(I+J),Dummy=1)
```
```
JOIN=RASTER%>%full_join(.,RASTER,by=“Dummy”)
```
```
COV=mutate(JOIN,distance=0.5*(abs(I.x-I.y)+abs
```
```
(J.x-J.y)+abs(K.x-K.y)),VALUE=abs(VALUE.x-VALUE.y))
```
```
COV=select(COV,DISTANCE,VALUE)
```
Set Operations: Set operations such as union and intersection are
foundational operations in the DGGS data model. The vectors are
converted to a set of DGGIDs in the DGGS data model and set operations
are straightforward to apply. Fig. 8 provides a visual representationof
```
IDEAS operations Union (Fig. 8a), Intersect (Fig. 8b), and clip (Fig. 8c).
```
##############Set OPERATIONS#####################
```
POLYGON_1=tbl(con,“POLYGON_1”)
```
```
POLYGON_1=select(POLYGON_1,DGGID)
```
```
POLYGON_2=tbl(con,“POLYGON_2”)
```
```
POLYGON_2=select(POLYGON_2,DGGID)
```
```
intersect=intersect(POLYGON_1,POLYGON_2)
```
```
union=union(POLYGON_1,POLYGON_2)
```
##############RASTER CLIP#########################
```
RASTER=tbl(con,“RASTER”)
```
```
RASTER=select(RASTER,DGGID)
```
```
POLYGON=tbl(con,“POLYGON”)
```
```
POLYGON=select(POLYGON,DGGID)
```
```
Buffer: Buffering is the creation of a zone within or outside of a GIS
```
object such as point, line or polygon. The buffering operation creates a
polygon object based on the buffer distance parameter. In the DGGS
data model any vector object consists of a set of DGG cells which on
their own do not possess any boundary identification. Therefore,
identification of boundaries is one of the more important parts of buf-
fering in a DGGS spatial object. We embedded the boundary informa-
```
tion in the data structure for polygons as auxiliary information (de-
```
```
scribed above). However, when a new polygon is created as a result of
```
any GIS operation it is necessary to recompute its attributes.
Fig. 5. IDEAS database structure.
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
222
##############BOUNDARY EXTRACTION##################
```
POLYGON=tbl(con,“POLYGON”)
```
```
NEIGHBOR=tbl(con,“NEIGHBOR”)
```
```
JOIN=POLYGON%>%inner_join(.,NEIGHBOR,by=c
```
```
(“DGGID”=“DGGID”))%>%left_join(.,POLYGON,by=c(“NEIG-
```
```
HBOR”=“DGGID”))
```
```
JOIN=JOIN%>%group_by(DGGID.x)%>%summarise
```
```
(.,count=n())
```
```
BOUNDARY=filter(JOIN,count<6)
```
##############BUFFER-
ING############################
```
JOIN=BOUNDARY%>%inner_join(.,NEIGHBOR,by=c
```
```
(“DGGID”=“DGGID”))
```
```
JOIN=select(JOIN,NEIGHBOR)
```
```
POLYGON=select(POLYGON,DGGID)
```
##############NEGATIVE BUFFERING###################
```
Fig. 6. GIS web application (a) architecture and (b) user interface example.
```
```
Fig. 7. Map algebra analysis on DGGS data structure (a) Local, (b) Focal, (c) Zonal, and (d) Global.
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
223
```
BUFFERED_POLY=setdiff(POLYGON,JOIN)
```
##############POSITIVE BUFFERING###################
```
BUFFERED_POLY=union(POLYGON,JOIN)
```
The boundary DGGS cells for polygons are identified by the char-
acteristics of having less than 6 neighbors. Further, when we add
neighbors specified by buffering units to the existing polygon DGGS set
```
the resulting set is equivalent to the buffered polygon (Fig. 8d).
```
Network Analysis: Several types of network analysis can be per-
formed based on the IDEAS spatial data model when key network at-
tributes are encoded as auxiliary information in the attribute table.
Here we show a simple way to identify nodes in a network based on
DGGS network data tables.
##############JUNCTION IDENTIFICATION##############
```
NETWORK_1=tbl(con,“NETWORK_1”)
```
```
NETWORK_2=tbl(con,“NETWORK_2”)
```
```
JUNCTION=intersect(NETWORK_1,NETWORK_2)
```
2.5.2. Algorithm performance analysis
In order to compare the performance of the DGGS implementations
of common GIS operations, they were compared to traditional geo-
metric spatial functions for a common data set. The test dataset con-
sisted of 100, 1000, 10,000, 100,000 and 1,000,000 points selected
randomly from within our study region, the Mackenzie basin in
northern Canada. For each dataset, a set of Voronoi polygons were
generated. These point and polygon data were then imported into the
IDEAS database as simple OGC geometry objects as well as being con-
verted into the IDEAS DGGS-based data model. Four GIS analysis op-
erations were run on each dataset and runtimes were extracted. Using
this method both analyses are run on the same machine which de-
creases the level of uncertainty in comparing different methods. Each
analysis was run 100 times and the average and standard deviation of
run times for each operation were computed. Fig. 9 presents the
average run times for different GIS operations on standard geometry
and IDEAS data models. The results demonstrate superior performance
of IDEAS compared to the traditional geometry data model. Also, it
shows that the algorithms built on this model scale very well with input
data volumes.
3. IDEAS case study
3.1. Dynamic modelling case study
Dynamic modelling of environmental processes such as hurricanes,
wildfires, and pest outbreaks are important applications of GIS-based
analysis. Yet tools for doing these types of analysis are ill-equipped for
handling big geospatial data. The unified spatial representation of a
DGGS data model as is provided in IDEAS facilitate dynamic modelling
with quickly updating datasets. In this case study we examine the
problem of wildfire modelling within IDEAS.
In order to model the complexities of wildfires, empirical and
```
physical models have been developed (Bakhshaii and Johnson, 2019).
```
Empirical models predict fire spread speed and flame size using weather
variables and fuel combustion data, while physical models model fire
```
behaviour using combustion chemistry and fluid dynamics (Hernández
```
```
Encinas et al., 2007; Quartieri et al., 2010). A third generation of
```
wildfire modelling combines physical and empirical models and the use
of environmental variables to update fire behavior over time. Cellular
```
automata (CA) modelling has been one modelling framework fre-
```
quently used to model complex spatially explicit dynamics which we
explore here in the context of wildfire modelling.
```
Cellular Automation (CA) is a discrete dynamic system which con-
```
```
sists of (1) cells which exist on a grid, (2) neighbours which are defined
```
```
for each cell, and (3) states which are defined by rules and are updated
```
at discrete time steps. In each grid system, the local interaction between
each cell and its neighbors defines the CA model. The number of
neighbors depends on the cell shape and grid characteristics which for a
hexagonal DGGS each cell has 6 neighbors. In CA modelling, the states
of cells change at discrete moments in time, which are defined by the
```
time steps of the model (Joel, 2007). While our case study application is
```
based on local neighbourhoods defined within a single Q2DI
```
Fig. 8. Geometrical operation (a) Union, (b) Intersection, (c) Clipping, and (d) Buffering.
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
224
quadrilateral and did not handle non-hexagon geometries, this could be
easily implemented via a precomputed neighbourhood table used to
identify each cell’s neighbours and transitions.
For modeling wildfire spread using a DGGS-based data model in a
“close to data” approach the following assumptions are made:
• Each cell can only burn once,
• If a cell starts to burn it will fully burn in one of the discrete timesteps and in each time step at least one cell fully burns,
```
• Each wildfire is impacted by a set of climatic, topographic and fuelrelated parameters (Barros and Pereira, 2014).
```
The following variables are frequently used in fire modeling: wind
speed/direction, slope, landuse and landcover and temperature.
Fig. 10a shows the CA model flowchart. In order to test the model a set
of test cases was developed and in each test case one of the parameters
were changed and the other parameters held constant. Fig. 10b shows a
```
test case study for an Alberta wildfire in 2016 in Canada; white hexagon
```
cells are the extracted fire boundary on the third day of Alberta wildfire
and the gray cells are the CA model results. As the graph in Fig. 10b
illustrates, the accuracy of the model after a certain number of itera-
tions increases. In each iteration a separate regression model is applied
on the boundary cells which, estimates the confidence level of each
cell’s fire prediction, and this result is used on next iterations.
The use of the IDEAS data model for dynamic CA modelling in a big
data platform can incorporate constantly updating data streams ob-
tained for key variables, with complex algorithms for learning and
updating CA rule sets. The main aim of this work is to explore the
possibility of running such spatial analysis on this system at scale.
Taking an in-database approach to CA modelling provides better per-
formance with larger datasets, and avoids unintended errors which
might be caused by data transformation between separate server and
modelling environments. Accessing data directly in a database en-
vironment facilitates the use of data by different models. In addition,
the use of the DGGS data model enables a portable data structure for
any database, as this data model only needs basic data types which are
already supported by most database systems, eliminating requirements
for geographical extensions.
4. Discussion
New analytics and spatial data models are required to accommodate
```
big spatial data (Li et al., 2016). This paper proposes a geospatial data
```
model, GIS algorithms, and user interaction tools based on a DGGS that
supports geospatial data analytics. While DGGS have been around for
decades, interest has gained momentum in recent years, as demon-
```
strated by the recent OGC abstract specification (Open Geographic
```
```
Consortium, 2018). DGGS in the literature to-date, is primarily dis-
```
cussed as a spatial referencing system, with few papers dealing with
how to operationalize them as data models for GIS, and how analytics
libraries can interact with DGGS data. This is the primary contribution
of this paper: we have shown that a DGGS-based GIS platform can
confer significant advantages in terms of next-generation GIS – as was
```
suggested recently by Goodchild (2018).
```
Firstly, DGGS provide a single spatial representation for geospatial
data. This means that algorithms can be designed on this representation
and can therefore incorporate a wide variety of native geospatial data
types. In the examples and case study explored here, we have used
polygon, raster, network, and point object data. The key challenge is in
how we represent objects within the DGGS. The IDEAS data model
takes a minimally structured approach, rather than trying to assume too
much about requirements for spatial object storage. Instead, we store a
base cellular representation that can be used to derive more complex
spatial/spatial–temporal objects through the use of key/value attribute
pairs. For example, polygon boundaries can be stored explicitly when
storing vector GIS data, and multiband raster data can store band in-
formation as auxiliary attribute data. Our design choices here favour
flexibility over prescription. We did not re-create existing spatial data
Fig. 9. Comparison of the GIS operation with traditional method vs. the IDEAS data model. The execution time is the log of the mean value of the measured runtime
```
for 100 loops for (a) Buffer, (b) Difference, (c) Clip, (d) Intersects.
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
225
```
models within a DGGS environment; a more flexible data model sup-
```
ports creation of new more complex and dynamic representations that
can incorporate a wide variety of data types, scales, and analytics. This
aspect of our research requires additional investigation and study.
Secondly, we have shown through fairly simple R commands we can
interact with the DGGS data to operationalize common GIS analysis
functions such as map algebra, buffering, and set operations.
Importantly, we showed that these functions outperform their equiva-
lent functions performed on standard geometry classes. The IDEAS
database was created on a Netezza analytics data warehouse appliance,
with parallelized data storage – yet could be implemented on any
variety of distributed or centralized data storage technologies that
support relational data tables. The advantages of Netezza include easy
parallelization via distribution to nodes and a wide variety of big-data
ready analysis functions built-in. This has significant potential for de-
veloping more complex machine learning models for big geospatial
datasets. As more algorithms are created for different types of analysis
on DGGS data, more analysis can be moved closer to the data, with
potential for performance gains and less risk of data loss during trans-
mission from client modelling software to database.
One additional advantage afforded by DGGS-based GIS analysis as
demonstrated by IDEAS is the capability to explicitly incorporate spa-
tial uncertainty into big geospatial data analysis. Data quality remains a
```
key challenge associated with big data (Goodchild, 2013). While all
```
spatial data are collected with some degree of accuracy, vector geo-
metry types relegate this information to metadata, which can be easily
ignored in downstream analysis. Explicitly mapping spatial uncertainty
to DGGS cell resolution provides an easy mechanism to ensure data do
not exhibit false precision. Further, boundary uncertainty can be
```
mapped to fuzzy boundary values using auxiliary attributes (Wang and
```
```
Hall, 1996), supporting a wide variety of fuzzy-GIS operations
```
```
(Schneider, 2014; Murgante and Casas, 2004).
```
Several limitations are evident in the current implementation of
IDEAS which should be discussed briefly. Firstly, a major bottleneck
remains data loading, which requires quantizing data and importing
data in the IDEAS database. The quantization step heavily depends on
which spatial sampling techniques are used and how they are para-
meterized. There is no single method available which can directly
transform raster or vector data to the IDEAS data model. Additionally,
since data are discrete most spatial functions must be treated as dis-
cretized functions. For example, for a function like buffer the buffer size
must be specified as a discrete number of cells. This can cause a level of
uncertainty when a user aims to use continuous values for such func-
tions. However, applying functions in a multi-resolution structure can
solve some of the issues. A continuous buffer distance can be approxi-
mated by finding the closest DGGS resolution to the buffer distance
precision and changing the feature’s DGGS resolution to the destination
resolution and calculate the buffer based on the destination resolution.
Several instances of exploiting different DGGS resolutions and parent/
child relationships in algorithms remain to be explored further.
Due to the limitations in current map rendering libraries, the vi-
sualization of DGGS cells is an obstacle in the implementation.
```
Fig. 10. In-database cellular automata model, (a) Schematic of the process flow for cellular automata forest fire model, (b) a snapshot of the simulation of 2013
```
Alberta fire event.
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
226
Currently most libraries which are developed for the DGGS construction
are based on C++ programming language and for the web develop-
```
ment environment (front end) there is not any explicitly DGGS im-
```
plementations. H3 has provided native integration of H3Hexagon layers
```
to the deck.gl (Uber, 2019) library which can only be used for the
```
aperture 7 DGGS. To overcome this limitation the rendering must be
done using regular hexagon geometries as vector cells on the client side
which can degrade performance. Augmenting hexagon-raster formats
offers a potential avenue for developing native DGGS rendering li-
```
braries (de Sousa and Leitão, 2018). Transmission of DGGS data during
```
rendering is also a potential bottleneck which may be addressed
```
through signal processing methods such as wavelet transforms (Amiri
```
```
et al., 2019).
```
5. Conclusions
Geospatial analytics in the big data era require flexible architectures
that can make maximum use of available data, scale well with data
volume, integrate with a variety of modelling frameworks, and provide
interactive data exploration and visualization tools for users. IDEAS
provides a consistent multiscale spatial representation, a discrete tem-
poral representations, and a modular data model. We have shown that
DGGS-based GIS show significant potential as a data model for geos-
patial analytics at scale. The system derives from a well-defined theo-
retical background suitable for a new-era of geospatial data storage and
analysis. The discrete representation results in efficient storage and
querying within traditional relational database systems, also enabling
much easier parallel processing compared to traditional spatial algo-
rithms. This research, we believe, opens up new research directions in
spatial algorithm development for DGGS data, visualization, and com-
plex modelling and analytics.
Declaration of Competing Interest
The authors declare that they have no known competing financial
interests or personal relationships that could have appeared to influ-
ence the work reported in this paper.
Acknowledgements
The authors thank the Global Water Futures research program for
funding this work under the Developing Big Data and Decision Support
Systems theme. We would also like to thank Fred Verbroom, Jorge
Gonzalez-Outeirino and ICT staff at Wilfrid Laurier University for
technical support throughout this project.
References
Aji, A., Wang, F., Vo, H., Lee, R., Liu, Q., Zhang, X., Saltz, J., 2013. Hadoop-GIS: A HighPerformance Spatial Data Warehousing System over MapReduce. Proceedings of the
VLDB Endowment. International Conference on Very Large Data Bases.Alborzi, H., Samet, H., 2000. Augmenting SAND with a spherical data model. Paper
presented at the First International Conference on Discrete Global Grids. SantaBarbara, California, March 26–28.
Alesheikh, A.A., Helai, H., 2002. Web GIS: technologies and its applications. Symposiumon Geospatial Theory, Processing and Applications.
Amiri, A.M., Alderson, T., Samavati, F., 2019. Geospatial data organization methods withemphasis on aperture-3 hexagonal discrete global grid systems. Cartogr. Int. J. Geogr.
```
Inform. Geovisual. 54 (1), 30–50.Amiri, A., Samavati, F., Peterson, P., 2015. Categorization and conversions for indexing
```
```
methods of discrete global grid systems. ISPRS Int. J. Geo-Inf. 4 (1), 320–336.https://doi.org/10.3390/ijgi4010320.
```
```
Appel, M., Pebesma, E., 2019. On-demand processing of data cubes from satellite imagecollections with the gdalcubes library. Data 4 (3), 92. https://doi.org/10.3390/
```
data4030092.Bakhshaii, A., Johnson, E.A., 2019. A review of a new generation of wildfire–atmosphere
```
modeling. Can. J. For. Res. 49 (6), 565–574. https://doi.org/10.1139/cjfr-2018-0138.
```
Barnes, Richard, 2016. dggridR: Discrete Global Grids for R. https://github.com/r-barnes/dggridR.
Barros, A.M.G., Pereira, J.M.C., 2014. Wildfire selectivity for land cover type: Does size
matter? PLoS ONE. https://doi.org/10.1371/journal.pone.0084760.Baumann, P., Mazzetti, P., Ungar, J., Barbera, R., Barboni, D., Beccati, A., et al., 2016. Big
```
Data Analytics for Earth Sciences: the EarthServer approach. Int. J. Digital Earth 9(1), 3–29. https://doi.org/10.1080/17538947.2014.1003106.
```
```
Baumer, B.S., 2019. A grammar for reproducible and painless extract-transform-loadoperations on medium data. J. Comput. Graph. Stat. 28 (2), 256–264. https://doi.
```
org/10.1080/10618600.2018.1512867.Baumgardner, J.R., Frederickson, P.O., 1985. Icosahedral discretization of the two-
```
sphere. SIAM J. Num. Anal. 22 (6), 1107–1114.Bhat, M.A., Shah, R.M., Bashir, A., 2011. Cloud Computing: A solution to Geographical
```
```
Information Systems (GIS). Int. J. Comput. Sci. Eng. 3 (2), 594–600.Bondaruk, B., Roberts, S., Robertson, C., 2019. Discrete global grid systems: operational
```
```
capability of the current state of the art. In: In: Fast, V., McKenzie, G., Sieber, R.(Eds.), Proceedings of the Conference on Spatial Knowledge and Information -
```
Canada, vol. 2323. pp. 1–9. http://ceur-ws.org/Vol-2323/SKI-Canada-2019-7-6-1.pdf.
Bush, I., 2016. OpenEAGGR Literature Review & Prototype Evaluation. Bristol. Retrievedfrom https://github.com/riskaware-ltd/open-eaggr/tree/master/Documents.
Cao, H., Wachowicz, M., 2019. The design of an IoT-GIS platform for performing auto-mated analytical tasks. Comput. Environ. Urban Syst. 74, 23–40. https://doi.org/10.
1016/j.compenvurbsys.2018.11.004.Comber, A., Wulder, M., 2019. Considering spatiotemporal processes in big data analysis:
```
Insights from remote sensing of land cover and land use. Trans. GIS 23 (5), 879–891.https://doi.org/10.1111/tgis.12559.
```
Commonwealth Computer Research Inc, 2019. GeoMesa User Manual. Retrieved fromhttps://www.geomesa.org/documentation/user/architecture.html.
Consortium, O.G., 2019. Topic 21: Discrete Global Grid Systems Abstract Specification.Retrieved from http://docs.opengeospatial.org/as/15-104r5/15-104r5.html.
Conway, J.H., Sloane, N.J.A., 1998. Sphere Packings, Lattices, and Groups.SpringerVerlag, New York, New York, pp. 679.
Craglia, M., de Bie, K., Jackson, D., Pesaresi, M., Remetey-Fülöpp, G., Wang, C., et al.,2012a. Digital Earth 2020: Towards the vision for the next decade. Int. J. Digital
```
Earth 5 (1), 4–21. https://doi.org/10.1080/17538947.2011.638500.Craglia, M., Goodchild, M.F., Annoni, A., Câmara, G., Gould, M.D., Kuhn, W., et al., 2008.
```
```
Next-Generation Digital Earth (Editorial). Int. J. Spat. Data Infrastruct. Res. 3,146–167. https://doi.org/10.2902/1725-0463.2008.03.art9.
```
Eldawy, A., 2014. SpatialHadoop: towards flexible and scalable spatial processing usingmapreduce. In: Proceedings of the 2014 SIGMOD PhD Symposium, https://doi.org/
10.1145/2602622.2602625.Esri, 2019. GIS Tools for Hadoop. Retrieved from https://esri.github.io/gis-tools-for-
hadoop/.Fekete, G., Treinish, L., 1990. Sphere quadtrees: A new data structure to support the
visualization of spherically distributed data. SPIE, Extract. Mean. Compl. Data:Process. Displ. Interact. 1259, 242–250.
Ferrari, L., Rosi, A., Mamei, M., Zambonelli, F., 2011. Extracting urban patterns fromlocation-based social networks. In: Proceedings of the 3rd ACM SIGSPATIAL
International Workshop on Location-Based Social Networks, pp. 9–16. https://doi.org/10.1145/2063212.2063226.
Francisco, P., 2011. The Netezza Data Appliance Architecture: A Platform for HighPerformance Data Warehousing and Analytics. IBM Redbook.
Fuller, R.B., 1975. Synergetics. MacMillan, New York, New York, pp. 876.Gandomi, A., Haider, M., 2015. Beyond the hype: Big data concepts, methods, and ana-
```
lytics. Int. J. Inf. Manage. 35 (2), 137–144. https://doi.org/10.1016/j.ijinfomgt.2014.10.007.
```
Gao, S., Goochild, M.F., 2013. Asking spatial questions to identify GIS functionality. In:Proceedings - 2013 4th International Conference on Computing for Geospatial
Research and Application, COM.Geo 2013. https://doi.org/10.1109/COMGEO.2013.18.
Gao, S., Li, L., Li, W., Janowicz, K., Zhang, Y., 2017. Constructing gazetteers from vo-lunteered Big Geo-Data based on Hadoop. Comput. Environ. Urban Syst. https://doi.
org/10.1016/j.compenvurbsys.2014.02.00.Gibb, R., Raichev, A., Speth, M., 2016. The rHEALPix discrete global grid system. In: IOP
Conference Series: Earth and Environmental Science, https://doi.org/10.1088/1755-1315/34/1/012012.
Giuliani, G., Chatenoux, B., De Bono, A., Rodila, D., Richard, J.-P., Allenbach, K., et al.,2017. Building an Earth Observations Data Cube: lessons learned from the Swiss Data
```
Cube (SDC) on generating Analysis Ready Data (ARD). Big Earth Data. https://doi.org/10.1080/20964471.2017.1398903.
```
```
Golay, J.E., 1969. Hexagonal parallel pattern transformations. IEEE Transactions onComputers C- 18 (8), 733–739.
```
```
Goodchild, M.F., 1994. Geographical grid models for environmental monitoring andanalysis across the globe (panel session). In: Proceddings of GIS/US '94 Conference,
```
```
Phoenix, Arizona.Goodchild, M.F., 2013. The quality of big (geo)data. Dial. Human Geogr. 3 (3), 280–284.
```
```
https://doi.org/10.1177/2043820613513392.Goodchild, M.F., 2018. Reimagining the history of GIS. Ann. Gis 24 (1), 1–8. https://doi.
```
org/10.1080/19475683.2018.1424737.Goodchild, M.F., Guo, H., Annoni, A., Bian, L., De Bie, K., Campbell, F., et al., 2012. Next-
generation digital earth. Proc. Natl. Acad. Sci. USA. https://doi.org/10.1073/pnas.1202383109.
Górski, K.M., Wandelt, B.D., Hivon, E., Hansen, F.K., Banday, A.J., 2018. The HEALPixPrimer. Retrieved from https://healpix.sourceforge.io.
```
Gotsman, C., Lindenbaum, M., 1996. On the metric properties of discrete space-fillingcurves. IEEE Trans. Image Process. 10 (1109/83), 499920.
```
```
Gregory, M.J., Kimerling, A.J., White, D., Sahr, K., 2008. A comparison of intercell me-trics on discrete global grid systems. Comput. Environ. Urban Syst. 32 (3), 188–203.
```
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
227
```
https://doi.org/10.1016/j.compenvurbsys.2007.11.003.Gruszczyński, W., Puniach, E., Ćwiąkała, P., Matwij, W., 2019. Application of convolu-
```
tional neural networks for low vegetation filtering from data acquired by UAVs.ISPRS J. Photogramm. Remote Sens. 158, 1–10. https://doi.org/10.1016/j.isprsjprs.
2019.09.014.Guan, H., Yu, Y., Ji, Z., Li, J., Zhang, Q., 2015. Deep learning-based tree classification
```
using mobile LiDAR data. Remote Sens. Lett. 6 (11), 864–873. https://doi.org/10.1080/2150704X.2015.1088668.
```
Guo, H., Liu, Z., Jiang, H., Wang, C., Liu, J., Liang, D., 2017. Big Earth Data: a newchallenge and opportunity for Digital Earth’s development. Int. J. Digital Earth 10
```
(1), 1–12. https://doi.org/10.1080/17538947.2016.1264490.Hahmann, S., Burghardt, D., 2013. How much information is geospatially referenced?
```
```
Networks and cognition. Int. J. Geograph. Inform. Sci. 27 (6), 1171–1189. https://doi.org/10.1080/13658816.2012.743664.
```
```
Hales, T.C., 2007. The Jordan curve theorem, formally and informally. Am. Math. Month.114 (10), 882–894.
```
Han, J., Kamber, M., Pei, J., 2012. Data cube technology. Data Min. https://doi.org/10.1016/b978-0-12-381479-1.00005-8.
Hernández Encinas, L., Hoya White, S., Martín del Rey, A., Rodríguez Sánchez, G., 2007.Modelling forest fire spread using hexagonal cellular automata. Appl. Math. Model.
```
31 (6), 1213–1227. https://doi.org/10.1016/j.apm.2006.04.001.Hu, F., Xia, G.-S., Hu, J., Zhang, L., 2015. Transferring deep convolutional neural net-
```
```
works for the scene classification of high-resolution remote sensing imagery. RemoteSens. 7 (11), 14680–14707. https://doi.org/10.3390/rs71114680.
```
Hughes, J.N., Annex, A., Eichelberger, C.N., Fox, A., Hulbert, A., Ronquest, M., 2015.GeoMesa: a distributed architecture for spatio-temporal fusion. Geosp. Inform. Fusion
Motion Video Anal. https://doi.org/10.1117/12.2177233.Ihaka, I., Gentelman, R., 1996. R: a language for data analysis and graphics. J. Comput.
Graph. Stat. 5, 299–314.Jendryke, M., Balz, T., McClure, S.C., Liao, M., 2017. Putting people in the picture:
Combining big location-based social media data and remote sensing imagery forenhanced contextual urban information in Shanghai. Comput. Environ. Urban Syst.
62, 99–112. https://doi.org/10.1016/j.compenvurbsys.2016.10.004.Jo, J., Lee, K.-W., 2018. High-Performance Geospatial Big Data Processing System Based
```
on MapReduce. ISPRS Int. J. Geo-Inf. 7 (10), 399. https://doi.org/10.3390/ijgi7100399.
```
Joel, L.S., 2007. Cellular Automata: A Discrete View of the World. John Wiley & Sons,Hoboken, NJ.
Kamel Boulos, M.N., Lu, Z., Guerrero, P., Jennett, C., Steed, A., 2017. From urbanplanning and emergency training to Pokémon Go: applications of virtual reality GIS
```
(VRGIS) and augmented reality GIS (ARGIS) in personal, public and environmentalhealth. Int. J. Health Geograph. 16 (1), 7. https://doi.org/10.1186/s12942-017-
```
0081-0.Kenner, H., 1976. Geodesic Math and How to Use It. University of California Press,
Berkeley, California, pp. 172.Kimerling, A.J., Sahr, K., White, D., Song, L., 1999. Comparing geometrical properties of
global grids. Cartogr. Geograph. Inform. Sci. https://doi.org/10.1559/152304099782294186.
```
Kitchin, R., 2014. Big Data, new epistemologies and paradigm shifts. Big Data Soc. 1 (1).https://doi.org/10.1177/2053951714528481.
```
Li, S., Dragicevic, S., Castro, F.A., Sester, M., Winter, S., Coltekin, A., et al., 2016.Geospatial big data handling theory and methods: A review and research challenges.
ISPRS J. Photogramm. Remote Sens. 115, 119–133. https://doi.org/10.1016/j.isprsjprs.2015.10.012.
Li, J., Meng, L., Wang, F.Z., Zhang, W., Cai, Y., 2014. A Map-Reduce-enabled SOLAP cubefor large-scale remotely sensed data aggregation. Comput. Geosci. 70, 110–119.
```
https://doi.org/10.1016/j.cageo.2014.05.008.Ma, X., Wu, Y.-J., Wang, Y., Chen, F., Liu, J., 2013. Mining smart card data for transit
```
riders’ travel patterns. Transp. Res. Part C: Emerg. Technol. 36, 1–12. https://doi.org/10.1016/j.trc.2013.07.010.
Ma, Y., Wu, H., Wang, L., Huang, B., Ranjan, R., Zomaya, A., Jie, W., 2015. Remotesensing big data computing: Challenges and opportunities. Future Gen. Comput. Syst.
51, 47–60. https://doi.org/10.1016/j.future.2014.10.029.Mahdavi-Amiri, A., Alderson, T., Samavati, F., 2015. A survey of digital earth. Comput.
```
Graph. (Pergamon) 53, 95–117. https://doi.org/10.1016/j.cag.2015.08.005.Miller, H.J., Goodchild, M.F., 2015. Data-driven geography. GeoJournal 80 (4), 449–461.
```
```
https://doi.org/10.1007/s10708-014-9602-6.Murgante, B., Casas, G.L., 2004. G.I.S. and Fuzzy Sets for the Land Suitability Analysis. In:
```
```
Laganá, A., Gavrilova, M.L., Kumar, V., Mun, Y., Tan, C.J.K., Gervasi, O. (Eds.),Computational Science and Its Applications – ICCSA 2004. Springer, Berlin
```
Heidelberg, pp. 1036–1045.Nativi, S., Mazzetti, P., Craglia, M., 2017. A view-based model of data-cube to support big
earth data systems interoperability. Big Earth Data. https://doi.org/10.1080/20964471.2017.1404232.
```
PROJ contributors, 2019. {PROJ} Coordinate Transformation Software Library. Retrievedfrom https://proj.org/.
```
Psomadaki, S., Tijssen, T., Baart, F., Oosterom, P., 2016. Using a space filling curve ap-proach for the management of dynamic point clouds. ISPRS Annals of the
Photogrammetry, Remote Sensing and Spatial. Inf. Sci. IV-2/W1. https://doi.org/10.5194/isprs-annals-IV-2-W1-107-2016.
Purss, M., Gibb, R., Samavati, F., Peterson, P., Rogers, J.A., Ben, J., Dow, C., 2017, Topic21: Discrete Global Grid Systems Abstract Specification OGC-15-104r5, Open
Geospatial Consortium. https://docs.opengeospatial.org/as/15-104r5/15-104r5.html.
Purss, M.B.J., Liang, S., Gibb, R., Samavati, F., Peterson, P., Dow, C., et al., 2017b.Applying discrete global grid systems to sensor networks and the Internet of Things.
```
In: 2017 IEEE International Geoscience and Remote Sensing Symposium (IGARSS),pp. 5581–5583. https://doi.org/10.1109/IGARSS.2017.8128269.
```
Purss, M.B.J., Peterson, P.R., Strobl, P., Dow, C., Sabeur, Z.A., Gibb, R.G., Ben, J., 2019.Datacubes: a discrete global grid systems perspective. Cartograph. Int. J. Geograph.
```
Inform. Geovis. 54 (1), 63–71. https://doi.org/10.3138/cart.54.1.2018-0017.Quartieri, J., Mastorakis, N.E., Iannone, G., Guarnaccia, C., 2010. A Cellular Automata
```
model for fire spreading prediction. International Conference on Urban Planning andTransportation - Proceedings.
R Core Team, 2018. R: A Language and Environment for Statistical Computing. RFoundation for Statistical Computing, Vienna, Austria.
Sadourny, R., Arakawa, A., Mintz, Y., 1968. Integration of the nondivergent barotropicvorticity equation with an icosahedral-hexagonal grid for the sphere. Mon. Weather
```
Rev. 96 (6), 351–356.Sahr, K., White, D., 1998. Discrete global grid systems. In: Weisberg, S. (Ed.), Computing
```
```
Science and Statistics (Volume 30): Proceedings of the 30th Symposium on theInterface, Computing Science and Statistics. Minneapolis, Minnesota, May 13–16.
```
Interface Foundation of North America, Fairfax Station, Virginia, pp. 269–278.Sahr, K., White, D., Kimerling, A.J., 2003. Geodesic discrete global grid systems. Cartogr.
```
Geograph. Inform. Sci. 30 (2), 121–134. https://doi.org/10.1559/152304003100011090.
```
```
Sahr, K., 2008. Location coding on icosahedral aperture 3 hexagon discrete global grids.Comput. Environ. Urban Syst. 32 (3), 174–187. https://doi.org/10.1016/j.
```
```
compenvurbsys.2007.11.005.Sahr, K., 218). DGGRID version 6.4 User Documentation for Discrete Global Grid
```
Generation Software. Retrieved from https://discreteglobalgrids.org/wp-content/uploads/2019/05/dggridManualV64.pdf.
```
Schneider, M., 2000. Finite resolution crisp and fuzzy spatial objects. In: Forer, P., Yeh,A.G.O., He, J. (Eds.), Proceedings of the 9th International Symposium on Spatial Data
```
Handling, Beijing, 10–12 August, 2000, pp. 5a.3–5a.17.Schneider, M., 2014. Spatial Plateau Algebra for implementing fuzzy spatial objects in
databases and GIS: Spatial plateau data types and operations. Appl. Soft Comput. 16,148–170. https://doi.org/10.1016/j.asoc.2013.11.021.
```
Sinton, D.F., 1978. In: Dutton, G. (Ed.), 7. Addison-Wesley, Reading: MA, pp. 1–19.Song, L., Kimerling, A.J., Sahr, K., 2002. Developing an equal area global grid by small
```
```
circle subdivision. Santa Barbara In: Goodchild, M.F., Kimerling, A.J. (Eds.), DiscreteGlobal Grids: A Web Book. University of California.
```
```
Craglia, M., Ostermann, F., Spinsanti, L., 2012b. Digital Earth from vision to practice:Making sense of citizen-generated content. Int. J. Digital Earth 2 (5), 398–416.
```
```
https://doi.org/10.1080/17538947.2012.712273.de Sousa, L.M., Leitão, J.P., 2018. HexASCII: A file format for cartographical hexagonal
```
```
rasters. Trans. GIS 22 (1), 217–232. https://doi.org/10.1111/tgis.12304.Thuburn, J., 1997. A PV-based shallow-water model on a hexagonal-icosahedral grid.
```
Mon. Weather Rev. 125, 2328–2347.Uber, 2019. WebGL2 powered geospatial visualization layers deck.gl. Retrieved from
```
https://github.com/uber/deck.gl.Wang, F., Hall, B., 1996. Fuzzy representation of geographical boundaries in GIS. Int. J.
```
```
Geograph. Inform. Sci. 10 (5), 573–590.Wang, S., Yuan, H., 2014. Spatial Data Mining. Int. J. Data Warehouse. Min. 10 (4),
```
50–70. https://doi.org/10.4018/ijdwm.2014100103.Webster, J., 2003. Cell complexes, oriented matroids and digital geometry. Theoret.
Comput. Sci. 305, 491–502.White, D., 2000. Global grids from recursive diamond subdivisions of the surface of an
```
octahedron or icosahedron. Environ. Monit. Assess. 64 (1), 93–103.White, D., Kimerling, A.J., Overton, W.S., 1992. Cartographic and geometric components
```
```
of a global sampling design for environmental monitoring. Cartogr. Geograph.Inform. Syst. 19 (1), 5–22.
```
White, D., Kimerling, A.J., Sahr, K., Song, L., 1998. Comparing area and shape distortionon polyhedralbased recursive partitions of the sphere. Int. J. Geograph. Inform. Sci.
12, 805–827.White, T., 2012. Hadoop: The definitive guide, fourth ed. Online. https://doi.org/citeu-
like-article-id:4882841.Wickham, H., 2017. Tidyverse: Easily install and load ’tidyverse’ packages. Retrieved 124
from https://CRAN.R-project.org/package=tidyverse.Wickham, H., Francois, R., 2016. Dplyr: A grammar of data manipulation. Retrieved 126
from https://CRAN.R-project.org/package=dplyr.Williamson, D.L., 1968. Integration of the barotropic vorticity equation on a spherical
```
geodesic grid. Tellus 20 (4), 642–653.Yao, X., Mokbel, M., Ye, S., Li, G., Alarabi, L., Eldawy, A., et al., 2018. LandQv2: A
```
```
MapReduce-Based System for Processing Arable Land Quality Big Data. ISPRS Int. J.Geo-Inf. 7 (7), 271. https://doi.org/10.3390/ijgi7070271.
```
```
Yasseri, T., Spoerri, A., Graham, M., Kertész, J., 2013. The most controversial topics inWikipedia: A multilingual and geographical analysis (arXiv E-Print No. 1305.5566).
```
Retrieved from http://arxiv.org/abs/1305.5566.
C. Robertson, et al. ISPRS Journal of Photogrammetry and Remote Sensing 162 (2020) 214–228
228