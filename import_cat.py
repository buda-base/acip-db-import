import os
import rdflib
from rdflib import Literal, Graph, Dataset
from rdflib.namespace import RDF, RDFS, SKOS, OWL, Namespace, NamespaceManager, XSD
from datetime import datetime
import random
import string
import csv
import hashlib
import sys

"""
I have a file "ALL catalog - Catalog.csv" with no header line. Let's refer to its columns as A, B, C, D, etc. for the sake of this prompt

The file represents a bibliographical catalog in the form of a tree structure through the first 7 columns (A to G). Each row has exactly one of these columns filled with an "X". It represents the depth in the tree. For instance

```
X,,,,,,topic
,X,,,,,subtopic
X,,,,,,another topic
```

etc.

the other important columns are:
- a title in column J
- the id of the author or topic in column N (not always present)
- the row id in column M
- the type in column I, which can have different values (comma-separated), but the important ones are "T" (topic), "X" (ignore), "C" (collection), "BioOf" (biography of)

In Python please write a script that:
- goes throught the catalog with an understanding of the tree structure, so that:
   * for each row, the value of the topic id (column N) of all the parents is known
   * if a row has a C in type (column I), consider it a leaf and ignore all sub-rows
- for each leaf row, call import_row(row, parent_topic_ids)

leaf rows are rows that are colletions (C in column I) or that have no sub-level. They can happen at any level
"""

IN_ENGLISH = [
    "S00200A",
    "S00199A",
    "R0050A",
    "S00069F",
    "S00034E",
    "S00041N",
    "S00038F",
    "S12361E",
    "S00071A",
    "S00205A",
    "S00036F",
    "S00039F",
]

PREDEFINED_MW = {
    "S00200A": "MW1AL4",
    "S00069F": "MW1AL1",
    "S00034E": "MW1AL5",
    "D84081": "MW1AL2",
    "S00205A": "MW1AL3",
    "D04849": "MW1ER25",
    "D79973": "MW19837",
    "D50934": "MW29329",
    "S25126": "MW12171",
    "SP06954": "MW20482",
    "D61732": "MW8LS26206"
}

MW_OUTLINES = {
    "D50934_v1": "MW29329_O29329_76985U",
    "D50934_v2": "MW29329_O29329_AZ4Z18",
    "D50934_v3": "MW29329_O29329_L3LMLK",
    "S00005N": "MW8LS26206_O8LS26206_6IP5TT",
    "S00038F": "MW8LS26206_O8LS26206_MTTJK3",
    "S00006N": "MW8LS26206_O8LS26206_X2C3Y3",
    "S00007N": "MW8LS26206_O8LS26206_SP3WLI",
    "S00021N": "MW8LS26206_O8LS26206_HZTNCZ",
    "S00008N": "MW8LS26206_O8LS26206_1ZCMVE",
    "R00003E1": "MW19837_6B2A7A",
    "R00003E2": "MW19837_5CDC20",
    "R00003E3": "MW19837_D72A7B",
    "R0002K": "MW29329_O29329_0JDJHN", 
    "R0002KH": "MW29329_O29329_CQKMHJ", 
    "R0002G": "MW29329_O29329_0LPVO1", 
    "R0002NG": "MW29329_O29329_O0EJQK", 
    "R0002C": "MW29329_O29329_O94V7W", 
    "R0002CH": "MW29329_O29329_N8UN2K", 
    "R0002J": "MW29329_O29329_6X7FY9", 
    "R0002NY": "MW29329_O29329_XIA8OB",
    "R0002T": "MW29329_O29329_GXIYBS",
    "R0002TH": "MW29329_O29329_8FASRI",
    "R0002D": "MW29329_O29329_EQ3OQF",
    "R0002N": "MW29329_O29329_CRGHAV",
    "R0002P": "MW29329_O29329_7SXAV2",
    "R0002PH": "MW29329_O29329_NLXCSH",
    "R0002B": "MW29329_O29329_6W7EXR",
    "R0002M": "MW29329_O29329_CL1ENK",
    "R0002TZ": "MW29329_O29329_LAFSEA",
    "R0002TS": "MW29329_O29329_LSTYC9",
    "R0002DZ": "MW29329_O29329_03JHI1", 
    "R0002W": "MW29329_O29329_KBSWIH",
    "R0002ZH": "MW29329_O29329_CFTL5S",
    "R0002Z": "MW29329_O29329_ATUWPT",
    "R0002'": "MW29329_O29329_8616UP",
    "R0002Y": "MW29329_O29329_X4W43K",
    "R0002R": "MW29329_O29329_OV6DQL",
    "R0002L": "MW29329_O29329_BFQ11B",
    "R0002SH": "MW29329_O29329_016DWW",
    "R0002S": "MW29329_O29329_V3A7N5",
    "R0002H": "MW29329_O29329_7I09RE",
    "R0002A": "MW29329_O29329_O8I247",
    "R0002VB": "MW29329_O29329_9P97S0",
    "R0002YRS": "MW29329_O29329_6672T4",
    "R0002PIC": "MW29329_O29329_VUUT68",
}

PREDEFINED_OUTLINES = {
    "D61732": "O8LS26206",
    "D79973": "O2CN6094",
    "D50934": "O29329"
}

GROUPS = {
    "D45233": [["SB25006-1"], ["SB25006-2"]],
    "D61732": [["S00005N", "S00038F", "S00006N", "S00007N", "S00021N", "S00008N"]],
    "D85829": [["S00060M", "S00061M", "S00062M", "S00063M"]],
    "D50960": [["S05412TL-1", "S05412TL-2"]],
    "D55579": [["S00982E1", "S00982E2", "S00982E3", "S00982E4"]],
    "D94929": [["S00995E", "S00996E", "S00997E", "S00998E"]],
    "D42036": [["S00967E", "S00968E", "S00969E", "S00970E", "S00971E", "S00972E", "S00973E", "S00974E"]],
    "D35909": [["S00195A1", "S00195M2", "S00195M3", "S00195M4", "S00195M5", "S00195M6"]],
    "D17118": [["S00001M1", "SE00001M2", "SL00001N2", "SE00001M3", "SL00001N3", "S00001I4", "S00001A5", "S00001A6", "S00001A7", "S00001A8"]],
    "D23629": [["SE00009M1", "SL00009N1", "S00009M2", "S00009M3", "S00009M4", "S00009M5", "S00009M6"]],
    "D51009": [["S06814-1"], ["S06814-2"]],
    "D57606": [["S00044M1", "S00044M2", "S00044M3", "S00044M4", "S00044M5", "S00044I6", "S00044M7", "S00044M8"]],
    "D88299": [["SE00070I1", "SE0070M2"]],
    "D88300": [["SL00070N1", "SL00070I2"]],
    "D04848": [["SE00023M1", "SE00023M2"]],
    "D04849": [["SL00023N1", "SL00023N2", "S00023N3", "S00023N4"]],
    "D79973": [["R00003E1"], ["R00003E2"], ["R00003E3"]],
    "D50934": [
        ["R0002K", "R0002KH", "R0002G", "R0002NG", "R0002C", "R0002CH", "R0002J", "R0002NY"],
        ["R0002T", "R0002TH", "R0002D", "R0002N", "R0002P", "R0002PH", "R0002B", "R0002M", "R0002TZ", "R0002TS"],
        ["R0002DZ", "R0002W", "R0002ZH", "R0002Z", "R0002'", "R0002Y", "R0002R", "R0002L", "R0002SH", "R0002S", "R0002H", "R0002A", "R0002VB", "R0002YRS", "R0002PIC"]
        ],
    "D84081": [["S00041N", "S00042N", "S00040N", "S00026N"]],
    "D76496": [["S00036F", "S00037N", "S00033N", "S00020N"]],
    "D04849": [["S00050M", "SL00023N1", "SE00023M1", "SL00023N2", "SE00023M2"], ["S00039F", "S00029N", "S00030N", "S00031N", "S00032N", "S00023N3", "S00023N4"]],
    "D11540": [["S19100E1"], ["S19100E2"], ["S19100E3"], ["S19100E4"], ["S19100E5"], ["S19100E6"], ["S19100E7"], ["S19100E8"]],
    "D59818": [["S19088E"], ["S19089"], ["S19090"], ["S19092E1"], ["S19092E2"], ["S19092E3"], ["S19092E4"], ["S19092E5"], ["S19097E"]],
    "D75239": [["S19086E", "S19087E"]],
    "D75240": [["S00839D1", "S00839E2"]],
    "D02161": [["S05587-1"], ["S05587-2"], ["S05587-3"], ["S05587-4"]],
    "D43855": [["SL0059I1"], ["SL0059E2"]],
    "D08589": [["S06850I1A", "S06850I1B"], ["SE06850A1"], ["SL06850I2"]],
    "D53759": [["SN06838I1", "SN06838I2"]],
    "D75904": [["S00302M", "S00303M"]],
    "D51010": [["S06814I2"], ["S06814I5"], ["S06814M6"], ["S06814I8"], ["S06814M9"], ["S06814M10"], ["S06814I1A"], ["S06814I11"], ["S06814I3"], ["S06814I4"]],
    "D05632": [["S00992E", "S0993E"]],
    "D69930": [["SN12135E", "SD12135E", "S12222E", "S12223E"]],
    "D95409": [["S05877M", "S12173E"]],
    "D41251": [["S05588-1", "S05588-2", "S05588-3"]],
    "D41252": [["S05589-1", "S05589-2", "S05589-3"]],
    "D37208": [["S06954E1", "S06954I2"]],
    "D59861": [["S5275M85-1", "S5275M85-2"]],
}

def get_random_id(length = 12):
    letters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

def add_id(g, e_lname, allid):
    id_r = BDR["ID"+e_lname[2:]+"_ALL001"]
    g.add((BDR[e_lname], BF.identifiedBy, id_r))
    g.add((id_r, RDF.type, BDR.IDALL))
    g.add((id_r, RDF.value, Literal(allid)))

def import_outline(allid):
    # 3 cases: 
    #   1. there is an existing outline for which we ingest content locations in the etexts
    ds = Dataset()
    bind_prefixes(ds)
    only_add_cl = False
    olname = "O1AL"+allid
    g = ds.graph(BDG[olname])
    ielname = "IE1AL"+allid
    rootmwlname = "MW1AL"+allid
    if allid in PREDEFINED_MW:
        rootmwlname = PREDEFINED_MW[allid]
    ofpath = fpath(olname, "outline")
    if allid in PREDEFINED_OUTLINES:
        only_add_cl = True
        # get the existing outline
        olname = PREDEFINED_OUTLINES[allid]
        ofpath = fpath(olname, "outline")
        ds.parse(ofpath, format="trig", publicID=BDG[olname])
        g = ds.graph(BDG[olname])
    else:
        # TODO: add outline boilerplate
        g.add((BDR[olname], BDO.outlineOf, BDR[rootmwlname]))
        g.add((BDR[olname], RDF.type, BDO.Outline))
        g.add((BDR[olname], BDO.authorshipStatement, Literal("Initial outline data imported from Asian Legacy Library.", lang="en")))
        g.add((BDA[olname], RDF.type, ADM.AdminData))
        g.add((BDA[olname], ADM.adminAbout, BDR[olname]))
        g.add((BDA[olname], ADM.metadataLegal, BDA.LD_BDRC_CC0))
        g.add((BDA[olname], ADM.status, BDA.StatusReleased))
        g.add((BDA[olname], ADM.graphId, BDG[olname]))
        g.add((BDA[olname], ADM.restrictedInChina, Literal(False)))
    lge = BDA["LG"+olname+"_"+get_random_id()]
    g.add((BDA[olname], ADM.logEntry, lge))
    g.add((lge, RDF.type, ADM.InitialDataImport if not only_add_cl else ADM.UpdateData))
    g.add((lge, ADM.logAgent, Literal("buda-scripts/imports/ACIP/import_cat.py")))
    g.add((lge, ADM.logMethod, BDA.BatchMethod))
    g.add((lge, ADM.logDate, Literal(datetime.now().isoformat(), datatype=XSD.dateTime)))
    outline_ids = GROUPS[allid]
    nb_vols = len(outline_ids)
    for vnumminusone, textidlist in enumerate(outline_ids):
        vnum = vnumminusone + 1
        mwvol = rootmwlname+"_"+olname+"_V"+str(vnum)
        nbtextsinvol = len(textidlist)
        if nbtextsinvol == 1:
            textid = textidlist[0]
            mwvol = mwlname = rootmwlname+"_"+olname+"_"+textid
            if textid in MW_OUTLINES:
                mwvol = MW_OUTLINES[textid]
            add_id(g, mwvol, textid)
        else:
            textid = allid+"_v"+str(vnum)
            if textid in MW_OUTLINES:
                mwvol = MW_OUTLINES[textid]
        if nb_vols > 1:
            cllname = "CL"+mwvol[2:]+"_"+ielname
            g.remove((BDR[cllname], None, None))
            g.add((BDR[mwvol], BDO.contentLocation, BDR[cllname]))
            g.add((BDR[cllname], RDF.type, BDO.ContentLocation))
            g.add((BDR[cllname], BDO.contentLocationInstance, BDR[ielname]))
            g.add((BDR[cllname], BDO.contentLocationVolume, Literal(vnum, datatype=XSD.integer)))
            g.add((BDR[cllname], BDO.contentLocationEndVolume, Literal(vnum, datatype=XSD.integer)))
            if not only_add_cl:
                if nbtextsinvol == 1:
                    g.add((BDR[mwvol], SKOS.prefLabel, Literal(TITLES[textidlist[0]], lang="bo-x-ewts")))
                g.add((BDR[mwvol], RDF.type, BDO.Instance))
                g.add((BDR[mwvol], BDO.partType, BDR.PartTypeVolume))
                g.add((BDR[mwvol], BDO.inRootInstance, BDR[rootmwlname]))
                g.add((BDR[mwvol], BDO.partOf, BDR[rootmwlname]))
                g.add((BDR[mwvol], BDO.partIndex, Literal(vnum, datatype=XSD.integer)))
                g.add((BDR[mwvol], BDO.partTreeIndex, Literal(str(vnum))))
        if nbtextsinvol > 1:
            for textnumminusone, textid in enumerate(textidlist):
                textnum = textnumminusone + 1
                mwlname = rootmwlname+"_"+olname+"_"+textid
                if textid in MW_OUTLINES:
                    mwlname = MW_OUTLINES[textid]
                add_id(g, mwlname, textid)
                cllname = "CL"+mwlname[2:]+"_"+ielname
                g.remove((BDR[cllname], None, None))
                g.add((BDR[mwlname], BDO.contentLocation, BDR[cllname]))
                g.add((BDR[cllname], RDF.type, BDO.ContentLocation))
                g.add((BDR[cllname], BDO.contentLocationInstance, BDR[ielname]))
                g.add((BDR[cllname], BDO.contentLocationVolume, Literal(vnum, datatype=XSD.integer)))
                g.add((BDR[cllname], BDO.contentLocationEtext, Literal(textnum, datatype=XSD.integer)))
                g.add((BDR[cllname], BDO.contentLocationEndEtext, Literal(textnum, datatype=XSD.integer)))
                if only_add_cl:
                    continue
                g.add((BDR[mwlname], SKOS.prefLabel, Literal(TITLES[textid], lang="bo-x-ewts")))
                g.add((BDR[mwlname], RDF.type, BDO.Instance))
                g.add((BDR[mwlname], BDO.partType, BDR.PartTypeText))
                g.add((BDR[mwlname], BDO.inRootInstance, BDR[rootmwlname]))
                g.add((BDR[mwlname], BDO.partOf, BDR[mwvol] if nb_vols > 1 else BDR[rootmwlname]))
                g.add((BDR[mwlname], BDO.partIndex, Literal(textnum, datatype=XSD.integer)))
                g.add((BDR[mwlname], BDO.partTreeIndex, Literal(str(vnum)+(".%02d" % textnum))))
    print("save "+olname)
    save_file(olname, "outline", ds)

def get_nb_pgs():
    res = {}
    with open("nbpgs.csv", 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            res[row[0]] = row[1]
    return res

NB_PGS = get_nb_pgs()
TITLES = {}

def process_catalog(file_path):
    global TITLES
    # Read the CSV file
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        rows = list(reader)
    
    # filling the titles (we have to do it separately for the outlines)
    for row in rows:
        TITLES[row[12]] = row[9]
    # Process the tree structure
    process_tree(rows, 0, len(rows), [], 0)

def process_tree(rows, start_idx, end_idx, parent_topic_ids, current_level):
    i = start_idx
    while i < end_idx:
        row = rows[i]
        
        # Determine the level of this row (which column has 'X')
        row_level = None
        for level in range(7):  # Columns A to G (0 to 6)
            if row[level] == 'X':
                row_level = level
                break
        
        # Skip if we couldn't determine the level or it's not at the expected level
        if row_level is None or row_level != current_level:
            i += 1
            continue
        
        # Get the type from column I (index 8)
        row_type = row[8] if len(row) > 8 else ""
        
        topic_id = None
        if "Auth" not in row[8] and "X" not in row[8] and "C" not in row[8]:
            # Get the topic ID from column N (index 13)
            topic_id = row[13] if len(row) > 13 else None
        
        # Create a list of all parent topic IDs plus this one if it exists
        current_topic_ids = parent_topic_ids.copy()
        
        # Check if this is a leaf node
        is_collection = "C" in row_type.split(",") if row_type else False
        
        # Find the next row at the same or lower level
        next_same_level_idx = end_idx
        for j in range(i + 1, end_idx):
            for level in range(7):
                if rows[j][level] == 'X':
                    if level <= row_level:
                        next_same_level_idx = j
                        break
                    break
            if next_same_level_idx != end_idx:
                break
        
        # Check if this is a leaf (either explicitly a collection or has no children)
        has_children = False
        if i + 1 < next_same_level_idx:
            for j in range(i + 1, next_same_level_idx):
                for level in range(7):
                    if rows[j][level] == 'X' and level == row_level + 1:
                        has_children = True
                        break
                if has_children:
                    break
        
        is_leaf = is_collection or not has_children
        
        if is_leaf:
            # This is a leaf node, call import_row
            import_row(row, current_topic_ids)
            if is_collection:
                import_outline(row[12])
        elif not is_collection:
            # This is a branch node, process its children
            if topic_id:
                for topic_id_ind in topic_id.split(","):
                    current_topic_ids.append(topic_id_ind)
            process_tree(rows, i + 1, next_same_level_idx, current_topic_ids, current_level + 1)
        
        # Move to the next node at this level
        i = next_same_level_idx

GIT_ROOT = "../../../tbrc-ttl/"
if len(sys.argv) > 1:
    GIT_ROOT = sys.argv[1]
GIT_REPO_SUFFIX = "-20220922"

PREFIXMAP = {
    "http://purl.bdrc.io/resource/": "bdr",
    "http://id.loc.gov/ontologies/bibframe/": "bf",
    "http://purl.bdrc.io/ontology/core/": "bdo",
    "http://purl.bdrc.io/admindata/": "bda",
    "http://purl.bdrc.io/ontology/admin/": "adm",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://purl.dila.edu.tw/resource/": "dila"
}

BDR_URI = "http://purl.bdrc.io/resource/"
BDR = Namespace(BDR_URI)
BDG = Namespace("http://purl.bdrc.io/graph/")
BF = Namespace("http://id.loc.gov/ontologies/bibframe/")
BDO = Namespace("http://purl.bdrc.io/ontology/core/")
BDA = Namespace("http://purl.bdrc.io/admindata/")
ADM = Namespace("http://purl.bdrc.io/ontology/admin/")

NSM = NamespaceManager(Graph())
NSM.bind("bdr", BDR)
NSM.bind("bdg", BDG)
NSM.bind("bdo", BDO)
NSM.bind("bf", BF)
NSM.bind("bda", BDA)
NSM.bind("adm", ADM)
NSM.bind("skos", SKOS)
NSM.bind("owl", OWL)
NSM.bind("rdfs", RDFS)

def bind_prefixes(g):
    g.bind("bdr", BDR)
    g.bind("bdo", BDO)
    g.bind("bda", BDA)
    g.bind("bdg", BDG)
    g.bind("bf", BF)
    g.bind("adm", ADM)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)

def get_random_id(length = 12):
    letters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

def fpath(e_lname, datatype):
    md5 = hashlib.md5(str.encode(e_lname))
    two = md5.hexdigest()[:2]
    os.makedirs(GIT_ROOT+datatype+"s"+GIT_REPO_SUFFIX+"/"+two+"/", exist_ok=True)
    filepathstr = GIT_ROOT+datatype+"s"+GIT_REPO_SUFFIX+"/"+two+"/"+e_lname+".trig"
    return filepathstr

def save_file(e_lname, datatype, ds):
    filepathstr = fpath(e_lname, datatype)
    print(filepathstr)
    ds.serialize(filepathstr, format="trig")

NOW_LIT = Literal(datetime.now().isoformat(), datatype=XSD.dateTime)
LGE = BDA["LG0AL0"]

def import_row(row, parent_topic_ids):
    if len(row) < 13:
        logging.error("row is too short")
        return
    # This is where you would implement your import logic
    title_ewts = row[9]
    row_id = row[12]
    default_id = "1AL"+row_id
    ie_lname = "IE"+default_id
    nb_vols = 1
    vols = ["VE"+default_id]
    if row_id in GROUPS:
        group_info = GROUPS[row_id]
        nb_vols = len(group_info)
        if nb_vols > 1:
            vols = []
            for i in range(nb_vols):
                vols.append("VE"+default_id+("_%04d" % (i+1)))
    # IE
    adm = BDA[ie_lname]
    ds = Dataset()
    ds.namespace_manager = NSM
    g = ds.graph(BDG[ie_lname])
    bind_prefixes(ds)
    add_id(g, ie_lname, row_id)
    g.add((adm, RDF.type, ADM.AdminData))
    g.add((adm, ADM.adminAbout, BDR[ie_lname]))
    g.add((adm, ADM.status, BDA.StatusReleased))
    g.add((adm, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((adm, ADM.access, BDA.AccessOpen))
    g.add((adm, ADM.archiveFilesAccess, BDA.AccessSameAsOnline))
    g.add((adm, ADM.sourceFilesAccess, BDA.AccessSameAsOnline))
    g.add((adm, ADM.graphId, BDG[ie_lname]))
    g.add((adm, ADM.restrictedInChina, Literal(False)))
    g.add((adm, ADM.logEntry, LGE))
    g.add((LGE, RDF.type, ADM.InitialDataImport))
    g.add((LGE, ADM.logAgent, Literal("buda-scripts/imports/ACIP/import_cat.py")))
    g.add((LGE, ADM.logMethod, BDA.BatchMethod))
    g.add((LGE, ADM.logDate, NOW_LIT))
    ie = BDR[ie_lname]
    g.add((ie, BDO.inCollection, BDR.PR1ER12))
    g.add((ie, RDF.type, BDO.EtextInstance))
    g.add((ie, BDO.etextInfo, Literal("Etext kindly provided by the Asian Legacy Library (ALL). BDRC would like to express its gratitude to ALL for their generous support and for making available these precious texts for users around the world.", lang="en")))
    for i, v_id in enumerate(vols):
        v = BDR[v_id]
        g.add((ie, BDO.instanceHasVolume, v))
        g.add((v, RDF.type, BDO.EtextVolume))
        g.add((v, BDO.volumeNumber, Literal(i+1, datatype=XSD.integer)))
    save_file(ie_lname, "einstance", ds)

    # MW
    mw_lname = "MW"+default_id
    if row_id in PREDEFINED_MW:
        mw_lname = PREDEFINED_MW[row_id]
        # don't create MW, WA, etc. in that case
        return

    mw = BDR[mw_lname]
    adm = BDA[mw_lname]
    ds = Dataset()
    ds.namespace_manager = NSM
    g = ds.graph(BDG[mw_lname])
    bind_prefixes(ds)
    g.add((adm, RDF.type, ADM.AdminData))
    g.add((adm, ADM.adminAbout, mw))
    g.add((adm, ADM.status, BDA.StatusReleased))
    g.add((adm, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((adm, ADM.graphId, BDG[mw_lname]))
    g.add((adm, ADM.restrictedInChina, Literal(False)))
    g.add((adm, ADM.logEntry, LGE))
    g.add((LGE, RDF.type, ADM.InitialDataImport))
    g.add((LGE, ADM.logAgent, Literal("buda-scripts/imports/ACIP/import_cat.py")))
    g.add((LGE, ADM.logMethod, BDA.BatchMethod))
    g.add((LGE, ADM.logDate, NOW_LIT))
    g.add((mw, RDF.type, BDO.Instance))
    g.add((mw, BDO.instanceHasReproduction, ie))
    if row_id in NB_PGS and int(NB_PGS[row_id]) > 2:
        nb_pages = NB_PGS[row_id]
        g.add((mw, BDO.extentStatement, Literal(f"{nb_pages} pp.")))    
    g.add((mw, BDO.biblioNote, Literal("Digital version in the ALL / ACIP database", lang="en")))
    g.add((mw, BDO.numberOfVolumes, Literal(len(vols), datatype=XSD.integer)))
    if row[9]:
        g.add((mw, SKOS.prefLabel, Literal(row[9], lang="bo-x-ewts")))
    if row[10]:
        g.add((mw, SKOS.altLabel, Literal(row[10], lang="en")))
    other_wa_lname = row[15]
    wa_lname = "WA"+default_id if not other_wa_lname else other_wa_lname
    if row[9]:
        g.add((mw, BDO.instanceOf, BDR[wa_lname]))
    save_file(mw_lname, "instance", ds)

    if other_wa_lname or not row[9]:
        return

    # WA
    wa_lname = "WA"+default_id
    wa = BDR[wa_lname]
    adm = BDA[wa_lname]
    ds = Dataset()
    ds.namespace_manager = NSM
    g = ds.graph(BDG[wa_lname])
    bind_prefixes(ds)
    g.add((adm, RDF.type, ADM.AdminData))
    g.add((adm, ADM.adminAbout, wa))
    g.add((adm, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((adm, ADM.status, BDA.StatusReleased))
    g.add((adm, ADM.graphId, BDG[wa_lname]))
    g.add((adm, ADM.restrictedInChina, Literal(False)))
    g.add((adm, ADM.logEntry, LGE))
    g.add((LGE, RDF.type, ADM.InitialDataImport))
    g.add((LGE, ADM.logAgent, Literal("buda-scripts/imports/ACIP/import_cat.py")))
    g.add((LGE, ADM.logMethod, BDA.BatchMethod))
    g.add((LGE, ADM.logDate, NOW_LIT))
    g.add((wa, RDF.type, BDO.Work))
    g.add((wa, SKOS.prefLabel, Literal(row[9], lang="bo-x-ewts")))
    if row[13]:
        p_lname_list = row[13].split(',')
        for i, p_lname in enumerate(p_lname_list):
            aac = BDR["CR"+wa_lname+f"_00{i+1}"]
            p = BDR[p_lname[4:]]
            g.add((wa, BDO.creator, aac))
            g.add((aac, BDO.agent, p))
            g.add((aac, BDO.role, BDR.R0ER0019))
            g.add((aac, RDF.type, BDO.AgentAsCreator))
    lang = BDR.LangBo
    if row_id in IN_ENGLISH:
        lang = BDR.LangEn
    g.add((wa, BDO.language, lang))
    for t_lname in parent_topic_ids:
        t = BDR[t_lname[4:]]
        g.add((wa, BDO.workIsAbout, t))
    save_file(wa_lname, "work", ds)

if __name__ == "__main__":
    # Replace with your actual file path
    file_path = "ALL catalog - Catalog.csv"
    process_catalog(file_path)