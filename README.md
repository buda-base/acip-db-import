# Deliverables of the ACIP database import project

The Asian Classics Input Project (ACIP) Database was imported on BDRC in October 2025 on https://purl.bdrc.io/resource/PR1ER12, thanks to the support of Diamond Cutter Institute and Asian Legacy Library.

This repository contains the deliverables of the project:

1. [Catalog.csv](Catalog.csv): the ACIP Sungbum catalog in spreadsheet format
2. [ACIP.py](ACIP.py): Python script to transform ACIP transliteration into Extended Wylie (EWTS), integrated into the open source library [pyewts](https://github.com/OpenPecha/pyewts)
3. [acip.js](acip.js): JavaScript port of the previous file, integrated into the open source library [jsewts](https://github.com/buda-base/jsewts), see [online demo](https://buda-base.github.io/jsewts/)
4. [import_cat.py](import_cat.py): Python file used by BDRC to import the ACIP catalog in the BDRC database
5. [convert.py](convert.py): Python file used by BDRC to convert the ACIP files into BDRC's etext archival format (TEI/XML)
6. [osmapping.json](osmapping.json): OpenSearch / ElasticSearch mapping file used by BDRC