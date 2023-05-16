# wingman

## Summary

This is a CLI tool that scans the filesystem of a cloud instance using grype without impacting performance or reliability. It works by taking a snapshot of the instance filesystem, creating a new instance to be scanned, scanning, and then exporting the results before destroying the scanner instance. Leaving the original resources untouched.

This first iteration only works with droplet (VMs) on Digital Ocean. If I keep working on it, future versions may include other types of resources and other clouds.

## Requirements

1. Python (Tested on 3.10)
2. python-digitalocean
3. OpenSSH

## How I wanted it to work

1. Take a snaphot of all running instances
2. Create volumes out of those running instances
3. Attach all those volumes to a scanning instance
4. Scan each of the attached volumes

## How it works on DO

I had to modify the process because a snapshot of a droplet can only be turned into another droplet and DO doesn't seem to have a way to run commands through the API:

1. Snapshot selected instances
2. Create a new SSH key just for the scanner
3. Create Droplets from each snapshot with the new public key
4. Install and Run Grype over SSH
5. Save results locally as JSON
6. Clean up snapshots, droplets and keys

## Usage
1. Clone the repository and cd into it
2. Install requirements
3. Add DO Access Token names `DO_ACCESS_TOKEN`
4. From `python3 main.py do` to scan all instances you have access to on DO


## TODO

1. Get individual instance scanning working
2. Run the scans asynchronously
