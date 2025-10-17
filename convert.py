import os
import re
import xml.sax.saxutils as saxutils
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
import hashlib
from ACIP import ACIPtoEWTS
import pyewts
import glob
from pathlib import Path
import logging
from tqdm import tqdm
import shutil
import csv

converter = pyewts.pyewts()

PAGE_COUNT = 0

def calculate_sha256(filepath):
    """
    Calculate SHA256 checksum of a file.
    
    Args:
        filepath (str): Path to the file
    
    Returns:
        str: SHA256 hexadecimal digest
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def is_valid_xml(xml_string):
    try:
        # Parse XML to validate it
        root = ET.fromstring(xml_string)
        
        # Use minidom to create a pretty-printed version
        parsed_xml = minidom.parseString(ET.tostring(root, encoding='unicode'))
        return True
    
    except Exception as e:
        return False

def validate_and_normalize_xml(xml_string):
    """
    Validates an XML string and returns a normalized, well-indented version.
    
    Args:
        xml_string (str): The XML string to validate and normalize
        
    Returns:
        Tuple[bool, str]: A tuple containing:
            - bool: True if valid XML, False otherwise
            - str: Normalized XML string if valid, error message if invalid
    """
    try:
        # Parse XML to validate it
        ET.register_namespace("", "http://www.tei-c.org/ns/1.0")
        root = ET.fromstring(xml_string)
        
        # Use minidom to create a pretty-printed version
        parsed_xml = minidom.parseString(ET.tostring(root, encoding='unicode'))
        #normalized_xml = parsed_xml.toprettyxml(indent="")
        
        # Remove extra blank lines that minidom sometimes adds
        #normalized_xml = '\n'.join([line for line in normalized_xml.split('\n') if line.strip()])
        return True, xml_string
    
    except Exception as e:
        logging.error(e)
        return False, f"Invalid XML: {str(e)}"

def balance_parentheses(text, c1, c2):
    """
    Balance parentheses in the text.
    
    Args:
        text (str): Input text
    
    Returns:
        str: Text with balanced parentheses
    """
    # Track open and closed parentheses
    open_count = text.count(c1)
    close_count = text.count(c2)
    
    # Add missing closing or opening parentheses
    if open_count > close_count:
        text += c1 * (open_count - close_count)
    elif close_count > open_count:
        text = c2 * (close_count - open_count) + text
    
    return text

def ACIP_transform(s, last_is_shad=False):
    s = ACIPtoEWTS(s)
    startswithspace = s.startswith(" ")
    s = converter.toUnicode(s)
    # normalize punctuation:
    s = s.replace("ང།", "ང་།")
    if startswithspace:
        s = ('་' if not last_is_shad else ' ')+s
    return s

def convert_text_components(text):
    tag_pattern = re.compile(r'(<[^>]+>)')
    
    def should_skip_tag(tag):
        return 'xml:lang="en"' in tag
    
    parts = tag_pattern.split(text)
    
    result = []
    skip = False
    last_is_shad = False
    
    for part in parts:
        if tag_pattern.match(part):  # It's a tag
            result.append(part)
            skip = should_skip_tag(part)
        else:  # It's text
            r = part if skip else ACIP_transform(part, last_is_shad)
            if last_is_shad:
                r = ' '+r
            last_is_shad = not skip and len(part) and part[-1] in [',', '`', '`', ';']
            r = saxutils.escape(r)
            result.append(r)
    
    return ''.join(result)

def convert_line(line_str, variant_mode=0):
    """
    Convert a single line to TEI-compatible text.
    
    Args:
        line_str (str): Input line to convert
        variant_mode (int): 0 = no variant processing, 
                             1 = choice/corr processing, 
                             2 = unclear/supplied processing
    
    Returns:
        str: Converted line with TEI markup
    """
    # Escape XML special characters

    line_str = line_str.strip(" \t\n\r")

    # add a tsheg at the end
    if line_str and (line_str[-1].isalpha() or line_str[-1] == "'"):
        line_str += ' '

    original_line_str = line_str
    
    line_str = balance_parentheses(line_str, '[', ']')

    # Add line breaks
    line_str = '<lb/>'+line_str

    line_str = line_str.replace('[?]', '<gap reason="illegible" unit="syllable" quantity="1"/>')
    
    # Handle parenthesized text as small text
    def replace_parentheses(match):
        if not match.group(1):
            return ''
        return f'<hi rend="small">{match.group(1)}</hi>'
    
    line_str = re.sub(r'\(([^)]*)\)', replace_parentheses, line_str, flags=re.DOTALL)

    # transform editorial comments [#...]
    line_str = re.sub(r'\[#(.*?)\]', r'<note type="editorial" xml:lang="en">\1</note>', line_str)
    line_str = line_str.replace("[LL]", '<note type="editorial" xml:lang="en">Landza script on page</note>')
    line_str = line_str.replace("[DR]", '<note type="editorial" xml:lang="en">picture on page</note>')
    line_str = line_str.replace('{DD}', '<note type="editorial" xml:lang="en">picture on page</note>')
    line_str = re.sub(r'\[DD\d?\] ?([^[]+)', r'<figure><head>\1</head></figure>', line_str)
    
    # Handle variant modes if specified
    if variant_mode == 1:
        # Replace (xxx)[yyy] with <choice>
        def replace_variant(match):
            orig = match.group(1).strip()
            corr = match.group(2).strip()
            
            # Ignore * at the beginning of corrections
            corr = corr.lstrip('*')
            
            # Add cert attribute for corrections ending with ?
            cert_attr = ' cert="low"' if corr.endswith('?') else ''
            corr = corr.rstrip('?')
            
            return f'<choice><orig>{orig}</orig><corr{cert_attr}>{corr}</corr></choice>'
        
        line_str = re.sub(r'(?:^|\s+)(\S+)\s*\[([^\]]+)\]', replace_variant, line_str)
    
    else:
        # Replace [xxx] with <unclear>
        def replace_unclear(match):
            text = match.group(1).strip()
            if text == '?':
                return '<gap reason="illegible" unit="syllable" quantity="1"/>'
            tlower = text.lower()
            if "page" in tlower or "text" in tlower or "missing "in tlower:
                return '<note type="editorial" xml:lang="en">'+saxutils.escape(text.strip(" #!*[]()&"))+'</note>'
            text = text.rstrip('?')
            return f'<unclear reason="illegible" cert="low">{text}</unclear>'
        
        line_str = re.sub(r'\[([^\]]+)\]', replace_unclear, line_str)

    line_str = convert_text_components(line_str)
    
    if not is_valid_xml("<p>"+line_str+"</p>"):
        #logging.warning("could not make valid XML from "+original_line_str)
        line_str = ACIP_transform(original_line_str).strip()
        line_str = saxutils.escape(line_str)
        return line_str

    return line_str.strip()

def parse_document(content):
    """
    Parse the document into a structured format with pages.
    
    Args:
        content (str): Full text content of the document
    
    Returns:
        list: List of page dictionaries with 'number' and 'content' keys
    """
    global PAGE_COUNT
    # Balance parentheses in the entire document
    content = balance_parentheses(content, '(', ')')
    
    # Split content by page markers
    page_splits = re.split(r'(@+\S+)', content)
    
    pages = []
    current_page = None
    current_content = []

    for part in page_splits:
        # Check if this is a page marker
        page_match = re.match(r'@+(\S+)', part)
        if page_match:
            if current_page is not None or current_content:
                pages.append({
                    'number': clean_page_number(current_page),
                    'content': current_content
                })
                PAGE_COUNT += 1
            current_content = []
            # Start new page
            current_page = page_match.group(1)
        else:
            # Accumulate content for current page
            if part.strip():
                # Split into paragraphs (double newlines)
                paras = [p.replace('\n', ' ').replace('  ', ' ').strip() for p in part.split('\n\n') if p.strip()]
                current_content.extend(paras)

    # Add last page if exists
    if current_page is not None or current_content:
        pages.append({
            'number': clean_page_number(current_page),
            'content': current_content
        })

    # if no first page and then 1a then 2a, then first page is 1a, then 1b then 2a
    if len(pages) > 2 and pages[0]['number'] is None and (pages[1]['number'] == '1a' or pages[1]['number'] == '1') and pages[2]['number'] == '2a':
        pages[0]['number'] = '1a'
        pages[1]['number'] = '1b'

    return pages

def clean_page_number(page_num):
    """Remove leading zeros from page number."""
    if page_num is None:
        return None
    page_num = page_num.lstrip('0').lower()
    page_num = re.sub(r'[^0-9ab]', '', page_num)
    return page_num

PROPER_EMENDATIONS = [
    "S00202E",
    "S00057M",
    "S00034N",
    "S00021N",
    "S00020N",
    "S00019N",
    "S00017N",
    "S00016N",
    "S00013N",
    "SP05939N",
    "ST00024N",
    "SL05414N"
]

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

def sanitize_str(s):
    """
    Cleanup string from weird characters
    """
    # First remove invalid XML control characters
    # XML 1.0 allows only these characters:
    # #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    #s = re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]', '', s)
    # we also just remove all non-ASCII characters (after a manual confirmation that they're all erroneous)
    s = re.sub(r'[^\x09\x0A\x0D\x20-\x7E]', '', s)
    # normalize line breaks:
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    # remove spaces after line break
    s = re.sub(r'\n +', '\n', s)
    # normalize spaces
    s = re.sub(r'  +', ' ', s)
    return s

def convert_file(input_path, output_path, ie_lname, ve_lname, ut_lname, title):
    """
    Convert a single text file to TEI XML.
    
    Args:
        input_path (str): Path to input text file
        output_path (str): Path to output XML file
    """
    basename = os.path.splitext(os.path.basename(input_path))[0]
    variant_mode = 1 if basename in PROPER_EMENDATIONS else 2
    lang = "en" if basename in IN_ENGLISH else "bo"
    # Read the entire file
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = sanitize_str(content)
    
    # Calculate SHA256 checksum
    file_checksum = calculate_sha256(input_path)
    
    # Get source filename (basename)
    src_filename = saxutils.escape(os.path.basename(input_path))
    
    # Parse document into pages
    pages = parse_document(content)
    
    # Create TEI XML structure
    tei_content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
        '  <teiHeader>',
        '    <fileDesc>',
        '       <titleStmt>',
        f'         <title>{title}</title>',
        '        </titleStmt>',
        '        <publicationStmt>',
        "          <p>File from the archive of the Buddhist Digital Resource Center (BDRC), converted into TEI from a file not created by BDRC.</p>",
        '        </publicationStmt>',
        '      <sourceDesc>',
        '        <bibl>',
        f'          <idno type="src_path">{ve_lname}/{src_filename}</idno>',
        f'          <idno type="src_sha256">{file_checksum}</idno>',
        f'          <idno type="bdrc_ie">http://purl.bdrc.io/resource/{ie_lname}</idno>',
        f'          <idno type="bdrc_ve">http://purl.bdrc.io/resource/{ve_lname}</idno>',
        f'          <idno type="bdrc_ut">http://purl.bdrc.io/resource/{ut_lname}</idno>',
        '        </bibl>',
        '      </sourceDesc>',
        '    </fileDesc>',
        '    <encodingDesc>',
        f'      <p>The TEI header does not contain any bibliographical data. It is instead accessible through the <ref target="http://purl.bdrc.io/resource/{ie_lname}">record in the BDRC database</ref>.</p>',
        '    </encodingDesc>',
        '  </teiHeader>',
        '  <text>',
        f'    <body xml:lang="{lang}">',
        '      <p xml:space="preserve">'
    ]

    # TODO: make the p, pb and first lb on the same txt line
    
    # Add pages and paragraphs
    for page in pages:
        is_blank = len(page['content']) == 1 and ("MISSING PAGE" in page['content'][0] or "BLANK PAGE" in page['content'][0] or "[BP]" in page['content'][0])
        pnum_attribute = "" if not page["number"] else f' n="{page["number"]}"'
        if is_blank:
            tei_content.append(f'<pb{pnum_attribute} rend="blank"/>')
            continue

        tei_content.append(f'<pb{pnum_attribute}/>')

        # Convert and add paragraphs
        for p in page['content']:
            converted_p = convert_line(p, variant_mode)
            if converted_p:
                tei_content.append(f'{converted_p}')
    
    # Finish TEI structure
    tei_content.extend([
        '</p>',
        '    </body>',
        '  </text>',
        '</TEI>'
    ])
    
    # Join the content
    xml_content = '\n'.join(tei_content)
    
    # Validate XML before writing
    valid_xml, indented_xml = validate_and_normalize_xml(xml_content)
    if not valid_xml:
        raise ValueError(f"Generated XML is not well-formed for {input_path}")
    
    # Write to output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(indented_xml)

def convert_file_not_transcript(input_path, output_path, ie_lname, ve_lname, ut_lname, title, lang="en"):
    """
    Convert a single text file to TEI XML.
    
    Args:
        input_path (str): Path to input text file
        output_path (str): Path to output XML file
    """
    # Read the entire file
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = sanitize_str(content)
    content = saxutils.escape(content)
    
    # Calculate SHA256 checksum
    file_checksum = calculate_sha256(input_path)
    
    # Get source filename (basename)
    src_filename = saxutils.escape(os.path.basename(input_path))

    # Create TEI XML structure
    tei_content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
        '  <teiHeader>',
        '    <fileDesc>',
        '       <titleStmt>',
        f'         <title>{title}</title>',
        '        </titleStmt>',
        '        <publicationStmt>',
        "          <p>File from the archive of the Buddhist Digital Resource Center (BDRC), converted into TEI from a file not created by BDRC.</p>",
        '        </publicationStmt>',
        '      <sourceDesc>',
        '        <bibl>',
        f'          <idno type="src_path">{ve_lname}/{src_filename}</idno>',
        f'          <idno type="src_sha256">{file_checksum}</idno>',
        f'          <idno type="bdrc_ie">http://purl.bdrc.io/resource/{ie_lname}</idno>',
        f'          <idno type="bdrc_ve">http://purl.bdrc.io/resource/{ve_lname}</idno>',
        f'          <idno type="bdrc_ut">http://purl.bdrc.io/resource/{ut_lname}</idno>',
        '        </bibl>',
        '      </sourceDesc>',
        '    </fileDesc>',
        '    <encodingDesc>',
        f'      <p>The TEI header does not contain any bibliographical data. It is instead accessible through the <ref target="http://purl.bdrc.io/resource/{ie_lname}">record in the BDRC database</ref>.</p>',
        '    </encodingDesc>',
        '  </teiHeader>',
        '  <text>',
        f'    <body xml:lang="{lang}">',
        '      <p xml:space="preserve">'
    ]
    
    tei_content.append(content)

    # Finish TEI structure
    tei_content.extend([
        '</p>',
        '    </body>',
        '  </text>',
        '</TEI>'
    ])
    
    # Join the content
    xml_content = '\n'.join(tei_content)
    
    # Validate XML before writing
    valid_xml, indented_xml = validate_and_normalize_xml(xml_content)
    if not valid_xml:
        raise ValueError(f"Generated XML is not well-formed for {input_path}")
    
    # Write to output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(indented_xml)

def main():
    """
    Convert all .txt files in 'texts/' to TEI XML in 'texts-tei/'.
    Create two variants for demonstration.
    """
    # Create output directory if it doesn't exist
    os.makedirs('texts-tei', exist_ok=True)
    
    # Process each text file
    for filename in os.listdir('texts'):
        if filename.endswith('.txt'):
            input_path = os.path.join('texts', filename)
            
            # Variant 1: no variant processing
            output_filename_1 = os.path.splitext(filename)[0] + '_base.xml'
            output_path_1 = os.path.join('texts-tei', output_filename_1)
            convert_file(input_path, output_path_1, variant_mode=0)
            
            # Variant 2: choice/corr processing
            output_filename_2 = os.path.splitext(filename)[0] + '_choice.xml'
            output_path_2 = os.path.join('texts-tei', output_filename_2)
            convert_file(input_path, output_path_2, variant_mode=1)
            
            # Variant 3: unclear/supplied processing
            output_filename_3 = os.path.splitext(filename)[0] + '_unclear.xml'
            output_path_3 = os.path.join('texts-tei', output_filename_3)
            convert_file(input_path, output_path_3, variant_mode=2)
            
            logging.info(f'Converted {filename} to multiple variants')

NOT_TRANSCRIPTS = [
    "S00200A", # MW1AL4
    "S00199A", # ?
    "R0050A", # ?
    "S00069F", # MW1AL1
    "S00034E", # MW1AL5
    "S00041N", # MW1AL2
    "S00038F", # ?
    "S00071A", #
    "S00205A", # MW1AL3
    "S12361E",
    "S00034F",
    "S00036F",
    "S00039F",
]

PREDEFINED_MW = {
    "S00200A": "MW1AL4",
    "S00069F": "MW1AL1",
    "S00034E": "MW1AL5",
    "S00041N": "MW1AL2",
    "S00205A": "MW1AL3",
    "D04849": "MW1ER25",
    "D79973": "MW19837",
    "D50934": "MW29329",
    "S25126": "MW12171",
    "SP06954": "MW20482",
    "D61732": "MW8LS26206"
}

MW_OUTLINES = {
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

TITLES = {}
with open("ALL catalog - Catalog.csv", 'r', encoding='utf-8') as file:
    reader = csv.reader(file)
    for row in reader:
        if row[9]:
            title = converter.toUnicode(row[9])
            TITLES[row[12]] = title
        else:
            TITLES[row[12]] = row[12]

def convert_all():
    rev_volume = {}
    for dnumber, vollist in GROUPS.items():
        nb_vols = len(vollist)
        for vol_i, txtlist in enumerate(vollist):
            for txt_i, txt in enumerate(txtlist):
                rev_volume[txt] = {"d": dnumber, "vol_i": vol_i+1, "txt_i": txt_i+1, "nbvols": nb_vols}
    txt_files = sorted(glob.glob("texts/*.txt"))
    for file_path in tqdm(txt_files):
        base = os.path.splitext(os.path.basename(file_path))[0]
        base = base.strip(" .")
        title = base
        if base in TITLES:
            title = TITLES[base]
        else:
            logging.warning("no title for "+base)
        default_id = "1AL"+base
        ie_lname = "IE"+default_id
        mw_lname = PREDEFINED_MW[base] if base in PREDEFINED_MW else "MW"+default_id
        ve_lname = "VE"+default_id
        ut_lname = "UT"+default_id+"_0001"
        if base in rev_volume:
            rev_volume_info = rev_volume[base]
            default_id = "1AL"+rev_volume_info["d"]
            ie_lname = "IE"+default_id
            mw_lname = PREDEFINED_MW[base] if base in PREDEFINED_MW else "MW"+default_id
            if rev_volume_info["nbvols"] > 1:
                ve_lname = "VE"+default_id+("_%04d" % rev_volume_info["vol_i"])
            else:
                ve_lname = "VE"+default_id
            ut_lname = "UT"+ve_lname[2:]+("_%04d" % rev_volume_info["txt_i"])
        path_to_output_file = Path(f"texts_converted/{ie_lname}/archive/{ve_lname}/{ut_lname}.xml")
        path_to_source_file = Path(f"texts_converted/{ie_lname}/sources/{ve_lname}/{base}.txt")
        path_to_output_file.parent.mkdir(parents=True, exist_ok=True)
        path_to_source_file.parent.mkdir(parents=True, exist_ok=True)
        # copy source file
        shutil.copy(file_path, path_to_source_file)
        #logging.info(f"Processing: {file_path}")
        try:
            if base not in NOT_TRANSCRIPTS:
                convert_file(file_path, str(path_to_output_file), ie_lname, ve_lname, ut_lname, title)
            else:
                convert_file_not_transcript(file_path, str(path_to_output_file), ie_lname, ve_lname, ut_lname, title)
            #logging.info(f"Successfully processed: {file_path}")
        except Exception as e:
            logging.error(f"Error processing {file_path}: {str(e)}")

if __name__ == '__main__':
    #main()
    #test_transform()
    #convert_file("texts/S00027M.txt", "test2.xml", "IE1ER24")
    #convert_file("test23.txt", "test23.xml", "IE1ER24", "VVV", "UTUTUT", "TITLE")
    #convert_file("texts/R0002K.txt", "R0002K.xml", "IE1ER24", "VVV", "UTUTUT", "TITLE")
    #convert_file_not_transcript("texts/S00034E.txt", "testinvalid.xml", "IE1ER24", "", "")
    convert_file("texts/S05650E.txt", "testinvalid.xml", "IE1ER24", "", "", "TITLE")
    #S00034E, S00205A
    # S12361E, SP25006, S05919E, S05302E
    convert_all()
    print("page count:")
    print(PAGE_COUNT)
