import os
import numpy as np
import pandas as pd
import sqlite3
import difflib

from .config import Config 

__all__ = ["readDetectionsIntoDatabase", "readTrackletsIntoDatabase", "readTracksIntoDatabase",
           "buildTrackletDatabase", "buildTrackDatabase", "attachDatabases",
           "_findNewLinesAndDeletedIndices", "_makeNewLinkageDataFrames"]

def readDetectionsIntoDatabase(detsFile, con,
                               detectionsTable=Config.detection_table,
                               diaSourcesTable=Config.diasources_table,
                               mappingTable=Config.mapping_table,
                               detsFileColumns=Config.detection_file_columns,
                               specialIds=Config.detection_file_special_ids,
                               readParams=Config.detection_file_read_params,
                               chunksize=10000, 
                               mapObjectIds=True):
    """
    Reads a full detection file into a database and creates a database view representative 
    of the input detections needed for MOPS to run. 

    The input detection file columns should contain the columns needed for MOPS to run. The
    column mapping can be defined using the detsFileColumns keyword argument. The keys to this
    dictionary are the required MOPS columns, the values to those keys should be headers in the 
    input detections file. See `Config.detection_file_columns`. 

    If the input detection file objectIds are not integer values MOPS will not be able to run. To
    map these to MOPS-friendly integer values use the mapObjectIds keyword argument. This will create
    a mapping table in the database. Additionally, if the input dataset has noise detections use the 
    specialIds dictionary (keys are the objectId in the detection file, values should be the desired 
    negative integers to map those objectIds to). 

    Parameters
    ----------
    detsFile : str
        Path to file containing detections. File should have header with column names.
    con : database connection
        Connection to sqlite3 database or equivalent.
    detectionsTable : str
        Detection table name. Default is `Config.detection_table`.
    diaSourcesTable : str
        DiaSources table name. Default is `Config.diasources_table`.
    mappingTable : str
        Mapping table name. If mapObjectIds is True, mapping table with objectId mapping will
        be created. Default is `Config.mapping_table.`
    detsFileColumns : dict
        Dictionary containing the column mappings of the input detection file to those needed 
        for MOPS to run. Default is `Config.detection_file_columns`. 
    specialIds : dict
        Dictionary containing special objectIds, such as those that designate noise. The keys of the
        dictionary should be the objectId in the input detection file, the values should be desired negative
        integer values. Default is `Config.detection_file_special_ids`.
    readParams : dict
        Dictionary of `Pandas.read_csv` keyword arguments to use when reading in the detections file.
        Default is `Config.detection_file_read_params`. 
    chunksize : int
        Read input detection file into database in sets of rows of chunksize. Useful for 
        big data sets. Default is 10000. 
    mapObjectIds : bool
        If input detection file objectIds are not integer values, set this to True to create 
        an objectId mapping. Default is True.

    Returns
    -------
    None

    """
    print("Reading {} into {} table".format(detsFile, detectionsTable))
    for chunk in pd.read_csv(detsFile, chunksize=chunksize, **readParams):
        chunk.to_sql(detectionsTable, con, if_exists="append", index=False)
    
    if mapObjectIds is True:
        print("Creating {} table".format(mappingTable))
        con.execute("""CREATE TABLE Mapping (objectId INTEGER PRIMARY KEY, {} VARCHAR)""".format(detsFileColumns["objectId"]))
        print("Mapping {} to MOPS-friendly integer objectIds".format(detsFileColumns["objectId"]))
        if specialIds is not None:
            objects = pd.read_sql("""SELECT DISTINCT {} FROM {}
                                     WHERE {} NOT IN ('{}')""".format(detsFileColumns["objectId"],
                                                                      detectionsTable,
                                                                      detsFileColumns["objectId"],
                                                                      "', '".join(specialIds.keys())), con)
            
            print("Found {} unique objectIds".format(len(objects)))
            print("Mapping the following specialIds to:")
            for key in specialIds:
                print("\t{} : {}".format(key, specialIds[key]))
            objects["objectId"] = objects.index + 1
            objects = objects.append(pd.DataFrame(zip(specialIds.keys(), specialIds.values()),
                                                  columns=[objects.columns[0], objects.columns[1]]))
        else:
            objects = pd.read_sql("""SELECT DISTINCT {} FROM {}""".format(detsFileColumns["objectId"],
                                                                          detectionsTable), con) 
            
            print("Found {} unique objectIds".format(len(objects)))                                                       
            objects["objectId"] = objects.index + 1

        print("Building {} table".format(mappingTable))
        objects.sort_values("objectId", inplace=True)
        objects.to_sql(mappingTable, con, index=False, if_exists="append")

        print("Creating {} view using the following columns:".format(diaSourcesTable))
        print("\tdiaId : {}".format(detsFileColumns["diaId"]))
        print("\tvisitId : {}".format(detsFileColumns["visitId"]))
        print("\tobjectId : {}".format(detsFileColumns["objectId"]))
        print("\tra : {}".format(detsFileColumns["ra"]))
        print("\tdec : {}".format(detsFileColumns["dec"]))
        print("\tmjd : {}".format(detsFileColumns["mjd"]))
        print("\tmag : {}".format(detsFileColumns["mag"]))
        print("\tsnr : {}".format(detsFileColumns["snr"]))

        con.execute("""CREATE VIEW {} AS
                            SELECT d.{} AS diaId,
                                   d.{} AS visitId,
                                   m.objectId AS objectId,
                                   d.{} AS ra,
                                   d.{} AS dec,
                                   d.{} AS mjd,
                                   d.{} AS mag,
                                   d.{} AS snr
                            FROM {} AS d
                            JOIN {} AS m ON 
                                d.{} = m.{}
                            ;""".format(diaSourcesTable,
                                        detsFileColumns["diaId"],
                                        detsFileColumns["visitId"],
                                        detsFileColumns["ra"],
                                        detsFileColumns["dec"],
                                        detsFileColumns["mjd"],
                                        detsFileColumns["mag"],
                                        detsFileColumns["snr"],
                                        detectionsTable,
                                        mappingTable,
                                        detsFileColumns["objectId"],
                                        detsFileColumns["objectId"]))
    else:
        print("Creating {} view using the following columns:".format(diaSourcesTable))
        print("\tdiaId : {}".format(detsFileColumns["diaId"]))
        print("\tvisitId : {}".format(detsFileColumns["visitId"]))
        print("\tobjectId : {}".format(detsFileColumns["objectId"]))
        print("\tra : {}".format(detsFileColumns["ra"]))
        print("\tdec : {}".format(detsFileColumns["dec"]))
        print("\tmjd : {}".format(detsFileColumns["mjd"]))
        print("\tmag : {}".format(detsFileColumns["mag"]))
        print("\tsnr : {}".format(detsFileColumns["snr"]))

        con.execute("""CREATE VIEW {} AS
                            SELECT d.{} AS diaId,
                                   d.{} AS visitId,
                                   d.{} AS objectId,
                                   d.{} AS ra,
                                   d.{} AS dec,
                                   d.{} AS mjd,
                                   d.{} AS mag,
                                   d.{} AS snr
                            FROM {} AS d
                            ;""".format(diaSourcesTable,
                                        detsFileColumns["diaId"],
                                        detsFileColumns["visitId"],
                                        detsFileColumns["objectId"],
                                        detsFileColumns["ra"],
                                        detsFileColumns["dec"],
                                        detsFileColumns["mjd"],
                                        detsFileColumns["mag"],
                                        detsFileColumns["snr"],
                                        detectionsTable))

    print("Done.")
    return 

def readTrackletsIntoDatabase(trackletFile, con, trackletIdOffset=0, chunksize=100000):
    
    for i, chunk in enumerate(pd.read_csv(trackFile, header=None, names=["diaId"], chunksize=chunksize)):        
        # Create an array of integer trackletIds
        trackletIds = np.arange(trackletIdOffset + (chunksize * i) + 1, len(chunk) + trackletIdOffset + (chunksize * i) + 1, dtype=int)
        # Read in the trackletFile where every row is a string of diaIds delimited by whitespace
        # Split the string of diaIds into separate columns and then stack the columns so that every tracklet has 
        # a row for every diaId
        chunk_df = pd.DataFrame(pd.DataFrame(chunk["diaId"].str.split(" ").tolist(), index=trackletIds).stack(), columns=["diaId"])
        chunk_df.reset_index(1, drop=True, inplace=True)
        chunk_df["trackletId"] = chunk_df.index
        chunk_df = chunk_df[["trackletId", "diaId"]]
        # Not all tracklets have the same number of detections, empty detections needs to be dropped
        chunk_df["diaId"].replace("", np.nan, inplace=True)
        chunk_df.dropna(inplace=True)
        
        # Save the resulting dataframe to a sql database
        chunk_df.to_sql("TrackletMembers", con, if_exists="append", index=False)
    return

def readTracksIntoDatabase(trackFile, con, trackIdOffset=0, chunksize=100000):
    
    for i, chunk in enumerate(pd.read_csv(trackFile, header=None, names=["diaId"], chunksize=chunksize)):        
        # Create an array of integer trackIds
        trackIds = np.arange(trackIdOffset + (chunksize * i) + 1, len(chunk) + trackIdOffset + (chunksize * i) + 1, dtype=int)
        # Read in the trackfile where every row is a string of diaIds delimited by whitespace
        # Split the string of diaIds into separate columns and then stack the columns so that every track has 
        # a row for every diaId
        chunk_df = pd.DataFrame(pd.DataFrame(chunk["diaId"].str.split(" ").tolist(), index=trackIds).stack(), columns=["diaId"])
        chunk_df.reset_index(1, drop=True, inplace=True)
        chunk_df["trackId"] = chunk_df.index
        chunk_df = chunk_df[["trackId", "diaId"]]
        # Not all tracks have the same number of detections, empty detections needs to be dropped
        chunk_df["diaId"].replace("", np.nan, inplace=True)
        chunk_df.dropna(inplace=True)
        
        # Save the resulting dataframe to a sql database
        chunk_df.to_sql("TrackMembers", con, if_exists="append", index=False)
    return

def buildTrackletDatabase(database, outDir):
    """
    Build tracklet database with AllTracklets and TrackletMembers table,
    and the Tracklets, CollapsedTracklets, PurifiedTracklets and 
    FinalTracklets views. 
    
    Parameter
    ---------
    database : str
        Database name
    outDir : str
        Path to desired out directory for the database
        
        
    Returns
    -------
    con : database connection
        Connection to the database
    databasePath : str
        Full path to database
    """
    database = os.path.join(os.path.abspath(outDir), "", database)
    con = sql.connect(database)
    
    print("Creating DiaSources table...")
    con.execute("""
        CREATE TABLE DiaSources (
            diaId INTEGER PRIMARY KEY,
            visitId INTEGER,
            objectId INTEGER,
            ra REAL,
            dec REAL,
            mjd REAL,
            mag REAL,
            snr REAL
        );
        """)

    print("Creating AllTracklets table...")
    con.execute("""
        CREATE TABLE AllTracklets (
            trackletId INTEGER PRIMARY KEY,
            linkedObjectId INTEGER,
            numLinkedObjects INTEGER,
            numMembers INTEGER,
            velocity REAL,
            rms REAL,
            night REAL,
            createdBy INTEGER,
            deletedBy INTEGER,
            _lineNum_1 INTEGER,
            _lineNum_2 INTEGER,
            _lineNum_3 INTEGER,
            _lineNum_4 INTEGER
        );
        """)

    print("Creating TrackletMembers table...")
    con.execute("""
        CREATE TABLE TrackletMembers (
            trackletId INTEGER,
            diaId INTEGER
        );
        """)

    print("Creating Tracklets view...")
    con.execute("""
        CREATE VIEW Tracklets AS
        SELECT * FROM AllTracklets
        WHERE createdBy = 1
        """)

    print("Creating CollapsedTracklets view...")
    con.execute("""
        CREATE VIEW CollapsedTracklets AS
        SELECT * FROM AllTracklets
        WHERE deletedBy = 2
        OR createdBy = 2
        """)

    print("Creating PurifiedTracklets view...")
    con.execute("""
        CREATE VIEW PurifiedTracklets AS
        SELECT * FROM AllTracklets
        WHERE deletedBy = 3
        OR createdBy = 3
        """)

    print("Creating FinalTracklets view...")
    con.execute("""
        CREATE VIEW FinalTracklets AS
        SELECT * FROM AllTracklets
        WHERE deletedBy = 4
        OR createdBy = 4
        """)

    print("")

    return con, database

def buildTrackDatabase(database, outDir):
    """
    Build track database with AllTracks and TrackMembers table,
    and the Tracks and FinalTracklets views.  
    
    Parameter
    ---------
    database : str
        Database name
    outDir : str
        Path to desired out directory for the database
        
        
    Returns
    -------
    con : database connection
        Connection to the database
    databasePath : str
        Full path to database
    """
    database = os.path.join(os.path.abspath(outDir), "", database)
    con = sql.connect(database)

    print("Creating AllTracks table...")
    con.execute("""
        CREATE TABLE AllTracks (
            trackId INTEGER PRIMARY KEY,
            linkedObjectId INTEGER,
            numLinkedObjects INTEGER,
            numMembers INTEGER,
            rms REAL,
            windowStart REAL,
            startTime REAL,
            endTime REAL,
            subsetOf INTEGER,
            createdBy INTEGER,
            deletedBy INTEGER,
            chiSqDec FLOAT,
            chiSqRa FLOAT,
            fitRange FLOAT,
            _lineNum_5 INTEGER,
            _lineNum_6 INTEGER
        );
        """)

    print("Creating TrackMembers table...")
    con.execute("""
        CREATE TABLE TrackMembers (
            trackId INTEGER,
            diaId INTEGER
        );
        """)

    print("Creating Tracks view...")
    con.execute("""
        CREATE VIEW Tracks AS
        SELECT * FROM AllTracks
        WHERE createdBy = 5
        """)

    print("Creating FinalTracks view...")
    con.execute("""
        CREATE VIEW FinalTracks AS
        SELECT * FROM AllTracks
        WHERE deletedBy = 6
        OR createdBy = 6
        """)

    print("")

    return con, database


def attachDatabases(con, databases):
    attached_names = []

    if len(databases) > 10:
        print "Warning: Cannot attach more than 10 databases..."
        print "Proceeding with the first 10 databases..."
        databases = databases[0:10]

    for i, window in enumerate(databases):
        attached_names.append("db%s" % i)
        print "Attaching %s to con as db%s..." % (window, i)
        con.execute("""ATTACH DATABASE '%s' AS db%s;""" % (window, i))
    return attached_names

def _findNewLinesAndDeletedIndices(file1, file2):
    """
    Find new lines and the indices of deleted lines between two files. Compares file one and 
    two, and return the new lines and their indices in file two and the indices of lines deleted in file one. 

    Parameters
    ----------
    parameter: (dtype) [default (if optional)], information

    file1 : str
        Path to file one
    file2 : str
        Path to file two
    
    Returns
    -------
    list
        A list of the new lines in file 2
    Numpy Array
        Indices (line numbers) of new lines in file 2
    Numpy Array
        Indices (line numbers) of lines deleted in file 1
    """
    file1In = open(file1, "r")
    file2In = open(file2, "r")
    
    # Here we use unified_diff. Unfortunately, at this stage ndiff would be more informative with
    #  regards to index tracking however it is dreadfully slow with big files due to a series 
    #  of internal nested for loops. 
    udiff = list(difflib.unified_diff(file1In.readlines(), file2In.readlines(), n=0))
    
    new_lines = []
    new_line_nums = []
    deleted_lines = []
    deleted_line_nums = []

    
    for line in udiff[2:]:
        line_elements = line.split()
        if line_elements[0] == '@@':
            file1_index = int(line_elements[1].split(",")[0][1:])
            file2_index = int(line_elements[2].split(",")[0][1:])
        else:
            if line_elements[0][0] == "+":
                # This line only exists in file two. 
                # Lets add this line to a list of newly 
                #  created lines. 
                new_lines.append(line[1:-2])
                new_line_nums.append(file2_index)
                file2_index += 1
            elif line_elements[0][0] == "-":
                # This line only exists in file one.
                # Lets append the index to our list of deleted
                #  line numbers.
                deleted_lines.append(line)
                deleted_line_nums.append(file1_index)
                file1_index += 1
            
    return new_lines, np.array(new_line_nums), np.array(deleted_line_nums)

def _makeNewLinkageDataFrames(newLines, linkageType="trackletId", createdBy=1, idStart=1):
    """
    Create a linkage members dataframe from a new set of lines.
    
    Parameter
    ---------
    newLines : list 
        List of strings with new linkages
    linkageType : str
        One of trackletId or trackId. Default is trackletId
    createdBy : int
        If linkage was created by findTracklets: 1, collapseTracklets: 2, purifyTracklets: 3,
        removeSubsets (on Tracklets): 4, linkTracklets: 5, removeSubsets (on Tracks): 6
    idStart : int
        Linkage ID number from which to start assigning new linkage IDs
        
    Returns
    -------
    `pandas.DataFrame`
        LinkageMembers DataFrame: Column of linkage IDs with one row per member detection ID
    `pandas.DataFrame`
        AllLinkages DataFrame: Column of linkage IDs with one row per linkage, with columns of createdBy and 
        numMembers
    """
    # Assign linkage ids 
    ids = np.arange(idStart, idStart + len(newLines), dtype=int)
    # Create a dataframe with new linkages
    # Read in the trackletFile where every row is a string of diaIds delimited by whitespace
    # Split the string of diaIds into separate columns and then stack the columns so that every tracklet has 
    # a row for every diaId
    linkageMembers = pd.DataFrame(newLines, columns=["diaId"])
    # Split string of diaIds and stack them 
    linkageMembers = pd.DataFrame(pd.DataFrame(linkageMembers["diaId"].str.split(" ").tolist(), index=ids).stack(), columns=["diaId"])
    # Reset the index to account for stacking
    linkageMembers.reset_index(1, drop=True, inplace=True)
    linkageMembers[linkageType] = linkageMembers.index
    linkageMembers = linkageMembers[[linkageType, "diaId"]]
    linkageMembers["diaId"].replace("", np.nan, inplace=True)
    linkageMembers.dropna(inplace=True)
    
    allLinkages = pd.DataFrame(linkageMembers[linkageType].unique(), columns=[linkageType])
    allLinkages["numMembers"] = linkageMembers[linkageType].value_counts().sort_index().values
    allLinkages["createdBy"] = np.ones(len(allLinkages), dtype=int)*createdBy
    allLinkages["deletedBy"] = np.zeros(len(allLinkages), dtype=int)
    
    return linkageMembers, allLinkages
