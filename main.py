#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path
from paramiko import SSHClient, AuthenticationException
from getpass import getpass
import json

# Path to the JSON configuration file
config_path = '/home1/rtc29/.petlab.json'


def load_config():
    if not os.path.isfile(config_path):
        print(f"Configuration file not found: {config_path}")
        return None
    with open(config_path, 'r') as file:
        config = json.load(file)
    return config


# Set dictionary with last name of PI's and their studies
# Scans are categorized on MR server by PI last name
pi_dict = {
    "cosgrove": ["bava_ptsd_aud", "fmozat_dex", "mukappa_aud", "pbr_app311_aud", "pbr_oud"],
    "davis": ["ekap_ptsd", "fpeb_bpd", "pbr_ed"],
    "esterlis": ["app311_fpeb", "app311_ket", "fpeb_abp_mdd" "sdm8_sdc", "sv2a_aging_mdd"],
    "zakiniaeiz": ["flb_aud"]
    }


def pi_study_match(study):
    if not isinstance(study, str):
        raise ValueError("Study name must be a string")
    for pi_name, study_name in pi_dict.items():
        if study in study_name:
            return pi_name, study
    # Only runs if no study is found in pi_dict values
    print(f"No matching PI found for the study: {study}")
    sys.exit(1)


def ask_confirmation(prompt, input_method=input, negative_action=None, negative_message=""):
    """
    Ask for confirmation with a given prompt.

    Parameters:
        prompt (str): The message to display asking for confirmation.
        input_method (function): The method to use for user input, defaults to built-in input function.
        negative_action (function): The action to take if the user responds negatively, defaults to None.
        negative_message (str): The message to display if the user responds negatively.

    Returns:
        bool: True if the user confirms, False otherwise.
    """
    choice = input_method(prompt).lower()
    while choice not in ("y", "n"):
        choice = input_method(f"You typed: {choice}, please enter only y or n: ")
    if choice == "y":
        return True
    elif choice == "n":
        if negative_action:
            negative_action()
        else:
            print(negative_message)
        return False


def resource_path(relative_path):
    # Get absolute path to resource, works for dev and for PyInstaller
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def ssh_connect(host, usr, pswd):
    client = SSHClient()
    host_file = resource_path("known_hosts")
    client.load_host_keys(host_file)
    try:
        client.connect(hostname=host, username=usr, password=pswd, timeout=2)
    except AuthenticationException:
        print("Authentication failed. Please check your credentials.")
        sys.exit(1)
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)
    return client


def ssh_command(client, cmd):
    try:
        stdin, stdout, stderr = client.exec_command(cmd)
        return stdout.readlines()
    except Exception as e:
        print(f"SSH command execution error: {e}")
        return []


def main():
    subject = input("Please enter subject PET ID: ")
    study_input = input("Please enter study name: ")
    try:
        pi, study = pi_study_match(study_input)
    except ValueError as e:
        print(e)
    scanner = input("Please enter MR Scanner: ").lower().replace(" ", "")
    mrrc_server = "shred.med.yale.edu"
    m_user = "petlab"
    config = load_config()
    if config is None:
        m_pswd = getpass("Please enter petlab password: ")
    else:
        m_pswd = config.get('petlab_password')
    client = ssh_connect(mrrc_server, m_user, m_pswd)

    try:
        cmd = f'/home/rtc29/codes/FindMyStudy {scanner} {pi} | grep -i "{scanner}_[[:alnum:]]*_[[:alnum:]]*"'
        scans_list = ssh_command(client, cmd)

        if not scans_list:
            print(f"No scans found for {pi} on {scanner}")
            sys.exit(1)
        print(f"Found these scans for PI: {pi}")
        print("Enter the number of the scan you'd like to transfer:")
        for i, scan in enumerate(scans_list, start=0):
            print(f"{i} ---> {scan.split()[0]} | {scan.split()[4]}")

        scan_index = int(input())
        scan_to_transfer = scans_list[scan_index].split()[0]
        mr_date = scan_to_transfer.split("_")[1]
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

    try:
        cmd = f'readlink -f /data1/{scanner}_transfer/{scan_to_transfer}'
        mr_file_path = ssh_command(client, cmd)[0].rstrip()
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

    client.close()

    # Pet Connect
    while True:
        if not study.endswith("_mr"):
            study = (f"{study}_mr")
        else:
            pass
        pet_dir = Path(f"/data8/data/{study}/{mr_date}_{subject}/3d_dicom")
        if pet_dir.exists():
            file_count = len(list(pet_dir.glob("[MS]R*")))
            if file_count > 1:
                if ask_confirmation(f"{pet_dir} exists and contains {file_count} MR files, would you like to continue anyways? (y/n) "):
                    break
                else:
                    print("Not continuing")
                    sys.exit(0)
        else:
            if ask_confirmation(f"Transfer location is set to: {pet_dir}, is this correct? (y/n) "):
                try:
                    pet_dir.mkdir(parents=True, exist_ok=True)
                    break
                except Exception as e:
                    print(f"Error occurred: {e}")
                    sys.exit(1)
            else:
                # Allow user to change study, mr_date, or subject
                study = input(f"Please enter the correct study name (current: {study}) or press Enter to keep it: ") or study
                mr_date = input(f"Please enter the correct MR date (current: {mr_date}) or press Enter to keep it: ") or mr_date
                subject = input(f"Please enter the correct subject ID (current: {subject}) or press Enter to keep it: ") or subject
    try:
        print(f"Initiating transfer of {scan_to_transfer} to {pet_dir}")
        subprocess.run(["rsync", "-aW", "--info=progress2", f"{m_user}@{mrrc_server}:{mr_file_path}/*", str(pet_dir)])
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
