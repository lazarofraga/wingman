"""
Digital Ocean module for scanning droplets with grype.
"""
import json
import logging
import os
import time
from pathlib import Path
from urllib.request import urlopen

import digitalocean
from prettytable import PrettyTable

logging.basicConfig(
    format="%(levelname)s:%(module)s:%(asctime)s:%(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

SNAPSHOT_TIMEOUT = 500
SCAN_ATTEMPTS = 3

access_token = os.getenv("DO_ACCESS_TOKEN")
if not access_token:
    raise ValueError(
        "DigitalOcean Access Token not found in environment variables. Please set DO_ACCESS_TOKEN."
    )

manager = digitalocean.Manager(token=access_token)


def take_snapshot(droplet, snapshot_name=None):
    """
    Start a droplet snapshot and wait for it to be finished.
    When it's finished, return snapshot object.
    """
    if not snapshot_name:
        snapshot_name = f'{droplet.name}-snapshot-{str(time.time()).split(".", maxsplit=1)[0]}'
    logging.info("Taking snapshot of %s", droplet.name)
    snapshot = droplet.take_snapshot(snapshot_name=snapshot_name)
    action_id = snapshot["action"]["id"]
    actions = droplet.get_actions()
    for action in actions:
        if action.id == action_id:
            action.load()
            while action.status == "in-progress":
                time.sleep(10)
                logging.debug("Waiting for %s snapshot to complete.", snapshot_name)
                action.load()
            logging.debug("Action status: %s", action.status)
    snapshots = manager.get_droplet_snapshots()
    for snapshot in snapshots:
        if snapshot_name == snapshot.name:
            return snapshot


def wait_for_droplet(droplet_object):
    """
    Waits for an action and updates the object until it's finished
    """
    logging.info("Waiting for action to complete.")
    # Wait for the Droplet to be ready
    actions = droplet_object.get_actions()
    for action in actions:
        action.load()
        while action.status and action.status == "in-progress":
            time.sleep(10)
            logging.debug("Waiting for action to complete.")
            action.load()
            #Fix when droplet create fails to properly start
        logging.debug("Action status: %s", action.status)


def create_snapshots(droplets):
    """
    Wrapper to take snapshots of a list of droplet objects.
    """
    logging.debug("Taking snapshot of droplets")
    snapshots = []
    for droplet in droplets:
        snapshots.append(take_snapshot(droplet))
    return snapshots


def create_scanner_key():
    """
    Create a new SSH key for this session
    """
    key_name = f'scanner_key_{str(time.time()).split(".", maxsplit=1)[0]}'
    logging.info("Generating new keys")
    os.system(f'ssh-keygen -t rsa -b 4096 -N "" -f ./{key_name} >> allout.txt')
    logging.info("Adding Scanner Key to DO")
    ssh_key = open(f"{key_name}.pub", encoding="utf-8").read()
    key = digitalocean.SSHKey(
        token=access_token, name=f"{key_name}", public_key=ssh_key
    )
    key.create()
    return key_name


def create_scanner_droplet(snapshot):
    """
    Create droplet from snapshot
    """
    snapshot.load()
    logging.info("Creating a droplet from snapshot: %s", snapshot.name)
    droplet = digitalocean.Droplet(
        token=access_token,
        name=f"{snapshot.name}-droplet",
        region=snapshot.regions[0],  # Example: "nyc3"
        image=snapshot.id,  # Use the snapshot ID found earlier
        size_slug="s-2vcpu-4gb",  # Example: "s-1vcpu-1gb"
        backups=False,
        ipv6=False,
        user_data=None,
        private_networking=None,
        monitoring=True,
        tags=["snapshot-droplet"],  # Example: ["tag1", "tag2"]
        ssh_keys=manager.get_all_sshkeys(),
    )
    droplet.create()
    wait_for_droplet(droplet)
    droplet.load()
    logging.info("Finished creating droplet: %s", droplet.name)
    return droplet


def install_grype_and_scan(droplet):
    """
    Install Grype on and scan the snapshot droplet
    """
    droplet.load()
    logging.info("Installing Grype on %s", droplet.name)
    ssh_command = f"ssh -o StrictHostKeyChecking=no root@{droplet.ip_address}"

    url = "https://raw.githubusercontent.com/anchore/grype/main/install.sh"
    # Download from URL and decode as UTF-8 text.
    with urlopen(url) as webpage:
        data = webpage.read().decode()

    # Save to file.
    with open("install.sh", "w", encoding="utf-8") as output:
        output.write(data)

    install_grype = f'{ssh_command} "bash -s" < install.sh > allout.txt 2>&1'
    os.system(install_grype)
    os.system("rm install.sh")
    result_path = f"{droplet.name.split('-snapshot')[0]}-result.json"
    Path(result_path).touch()
    run_grype = f'{ssh_command} "./bin/grype / -o json" >> {result_path} 2>> allout.txt'
    logging.info("Scanning %s", droplet.name)
    os.system(run_grype)


def clean_up(scan_targets, snapshots, scanner_key):
    """
    Delete all the resources created for the scan
    """
    for droplet in scan_targets:
        droplet.load()
        logging.info("Deleting scanner droplet with ID: %s and name: %s", droplet.id, droplet.name)
        droplet.destroy()

    for snapshot in snapshots:
        snapshot.load()
        logging.info(
            "Deleting scanner snapshot with ID: %s and name: %s", snapshot.id, snapshot.name
        )
        snapshot.destroy()

    keys = manager.get_all_sshkeys()
    for key in keys:
        if key.name == scanner_key:
            logging.info("Destroying key: %s", key.name)
            digitalocean.SSHKey.destroy(key)

    os.system(f"rm {scanner_key}")
    os.system(f"rm {scanner_key}.pub")


def parse_results(droplet_name):
    """
    Parse scan results
    """
    filename = f"{droplet_name.split('-snapshot')[0]}-result.json"

    with open(filename, encoding="utf-8") as f:
        results = json.load(f)

    finding_counts = {}
    for match in results["matches"]:
        severity = match["vulnerability"]["severity"]
        try:
            finding_counts[severity] += 1
        except KeyError:
            finding_counts[severity] = 1
    return finding_counts


def print_results(droplets):
    """
    Print a table of scan results
    """
    table = PrettyTable()
    table.field_names = [
        "Droplet Name",
        "Critical",
        "High",
        "Medium",
        "Low",
        "Total",
    ]
    for droplet in droplets:
        results = parse_results(droplet.name)
        name = droplet.name.split("-snapshot")[0]
        critical = results.get("Critical", 0)
        high = results.get("High", 0)
        medium = results.get("Medium", 0)
        low = results.get("Low", 0)
        total = sum(results.values())
        table.add_row([name, critical, high, medium, low, total])
    print(table)


def scan_droplets(droplet_ids=None):
    """
    Start a scan of all accessible droplets
    """
    # Get all Droplets
    if not droplet_ids:
        logging.info("Getting all droplets")
        droplets = manager.get_all_droplets()
    else:
        droplets = []
        for droplet_id in droplet_ids:
            try:
                droplet = manager.get_droplet(droplet_id=droplet_id)
                droplets.append(droplet)
            except:
                raise ValueError(f"Unable to find droplet by id: {droplet_id}")
    logging.info("Preparing to Scan %s droplet(s)", len(droplets))



    # Create New Scanner Key and Add Scanner Key to DO
    scanner_key = create_scanner_key()

    # Snapshot All Droplets
    snapshots = create_snapshots(droplets)

    # Create Droplets from Snapshots
    scan_targets = []
    for snapshot in snapshots:
        scan_targets.append(create_scanner_droplet(snapshot))

    # Install and run Grype on new droplets

    # Making sure SSH has time to come up
    time.sleep(60)

    for droplet in scan_targets:
        install_grype_and_scan(droplet)

    # Clean up resources
    clean_up(scan_targets, snapshots, scanner_key)

    logging.info("Finished")

    print_results(scan_targets)


def scan(instance_ids=None):
    """
    Start a scan of some or all instances based on input
    """
    # Check if instance_ids are provided
    if instance_ids:

        logging.info('Running tool against DO droplets with ids: %s', ", ".join(instance_ids))
        scan_droplets(instance_ids)
    else:
        logging.info("Running tool against all DO Droplets.")
        scan_droplets()


def list_instances():
    """
    Create a list of all accessible instances
    """
    all_droplets = manager.get_all_droplets()

    table = PrettyTable()
    table.field_names = ["Id", "Region", "Name", "Size", "Disk"]

    for droplet in all_droplets:
        table.add_row(
            [
                droplet.id,
                droplet.region["slug"],
                droplet.name,
                droplet.size["slug"],
                droplet.size["disk"],
            ]
        )
    print(table)