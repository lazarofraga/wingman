# wingman

## Summary

This is a CLI tool that scans the filesystem of a cloud instance using grype while attempting to minimize the impact on the target resources. 

It works by taking a snapshot of the instance filesystem, creating a new instance to be scanned, scanning, and then exporting the results before destroying the scanner instance. Leaving the original resources untouched.

This first iteration only works with droplets (VMs) on Digital Ocean.

## Requirements

1. Python and pip (Tested on 3.10)
2. Python packages: python-digitalocean, prettytable
3. Linux system with OpenSSH (Not tested on Windows or Mac yet)

## Installation

1. `git clone https://github.com/lazarofraga/wingman.git`
2. `cd wingman`
3. `pip install -r requirements.txt`

## Access Token

Set the DO_ACCESS_TOKEN:
`export DO_ACCESS_TOKEN=<token_goes_here>`

## Usage

### List Instances

`python3 main.py do -l`

### Scan Instance(s) by ID

`python3 main.py do -i 1234567,1234568`

### Scan all Instances

`python3 main.py do`
