# AWS Python general purpose scripts

## s3_zip_ship.py
download all objects from any number of buckets (matching a prefix), archiving and migrating to a destination bucket

### Installation
Install required packages<br>
`pip install -r s3_zip_ship_requirements.txt`

### Usage
Get current state<br>
`python s3_zip_ship.py -s my-buckets -t`