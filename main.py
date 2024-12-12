#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path
from paramiko import SSHClient, AuthenticationException
from getpass import getpass
import json

# Path to the JSON configuration file containing credentials
config_path = '/home1/rtc29/.petlab.json'


def load_config():
    """
    Load configuration data from a JSON file.

    Returns:
        dict: A dictionary containing configuration values, or None if the file is not found.
    """
    if not os.path.isfile(config_path):  # Check if the config file exists
        print(f"Configuration file not found: {config_path}")
        return None
    with open(config_path, 'r') as file:
        config = json.load(file)  # Parse JSON config
    return config


# Set dictionary with last name of PI's (Principal Investigators) and their associated studies.
# Scans are categorized on MR server by PI last name.
pi_dict = {
    "cosgrove": ["bava_ptsd_aud", "fmozat_dex", "mukappa_aud", "pbr_app311_aud", "pbr_oud"],
    "davis": ["ekap_ptsd", "fpeb_bpd", "pbr_ed"],
    "esterlis": ["app311_fpeb", "app311_ket", "fpeb_abp_mdd", "sdm8_sdc", "sv2a_aging_mdd"],
    "zakiniaeiz": ["flb_aud"]
    }


def pi_study_match(study):
    """
    Match the study to the corresponding PI (Principal Investigator).

    Args:
        study (str): Study name to match.

    Returns:
        tuple: (pi_name, study) if a match is found.

    Raises:
        ValueError: If the study name is not found in the dictionary.
    """
    if not isinstance(study, str):
        raise ValueError("Study name must be a string")
    # Remove the "_mr" suffix if it exists, only for this check
    if study.endswith("_mr"):
        study = study[:-3]  # Remove last 3 characters (i.e., "_mr")
    # Look for the study in the dictionary and return the associated PI name
    for pi_name, study_name in pi_dict.items():
        if study in study_name:
            return pi_name, study
    # If no match is found, print error and exit
    print(f"No matching PI found for the study: {study}")
    sys.exit(1)


def ask_confirmation(prompt, input_method=input, negative_action=None, negative_message=""):
    """
    Ask for user confirmation with a given prompt.

    Args:
        prompt (str): The message to display asking for confirmation.
        input_method (function): The method to use for user input, defaults to built-in input function.
        negative_action (function): The action to take if the user responds negatively, defaults to None.
        negative_message (str): The message to display if the user responds negatively.

    Returns:
        bool: True if the user confirms, False otherwise.
    """
    choice = input_method(prompt).lower()  # Get user input and normalize to lowercase
    while choice not in ("y", "n"):  # Keep asking if invalid input is provided
        choice = input_method(f"You typed: {choice}, please enter only y or n: ")
    if choice == "y":
        return True
    elif choice == "n":
        if negative_action:
            negative_action()  # Perform action if the user selects 'n'
        else:
            print(negative_message)  # Default message when 'n' is selected
        return False


def resource_path(relative_path):
    """
    Get the absolute path to a resource, accounting for PyInstaller packaging.

    Args:
        relative_path (str): The relative path to the resource.

    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller sets the path to the bundled files in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")  # Default to current working directory if not using PyInstaller
    return os.path.join(base_path, relative_path)


def ssh_connect(host, usr, pswd):
    """
    Establish an SSH connection to a remote host.

    Args:
        host (str): The hostname or IP address of the remote server.
        usr (str): The username for authentication.
        pswd (str): The password for authentication.

    Returns:
        SSHClient: An SSH client instance connected to the remote host.

    Raises:
        AuthenticationException: If authentication fails.
        Exception: For other connection issues.
    """
    client = SSHClient()
    host_file = resource_path("known_hosts")  # Path to known hosts file
    client.load_host_keys(host_file)  # Load known hosts to verify the server
    try:
        # Attempt to connect using provided credentials
        client.connect(hostname=host, username=usr, password=pswd, timeout=2)
    except AuthenticationException:
        print("Authentication failed. Please check your credentials.")
        sys.exit(1)  # Exit if authentication fails
    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)  # Exit if connection fails
    return client


def ssh_command(client, cmd):
    """
    Execute a command on the remote server via SSH.

    Args:
        client (SSHClient): The SSH client connected to the remote host.
        cmd (str): The command to execute on the remote host.

    Returns:
        list: The output of the command from stdout.

    Raises:
        Exception: If an error occurs during command execution.
    """
    try:
        # Execute the SSH command and capture stdin, stdout, stderr
        stdin, stdout, stderr = client.exec_command(cmd)
        stdout_output = stdout.readlines()  # Capture standard output
        stderr_output = stderr.readlines()  # Capture standard error output

        # If there is any error output, print it to stderr
        if stderr_output:
            print(f"Error occurred during execution:\n{''.join(stderr_output)}", file=sys.stderr)

        return stdout_output  # Return the standard output
    except Exception as e:
        print(f"SSH command execution error: {e}", file=sys.stderr)
        return []  # Return an empty list if there's an error


def main():
    """
    Main function to execute the transfer of scans between systems.

    1. Prompts the user for subject ID, study name, MR scanner type, etc.
    2. Validates the study name to find the associated PI.
    3. Connects to the MR server and fetches the scan information.
    4. Validates or creates the necessary directories for storing data.
    5. Transfers the selected scan using rsync.
    """
    subject = input("Please enter subject PET ID: ")
    study_input = input("Please enter study name: ")
    pi, study = None, None  # Default to None if no match found
    try:
        pi, study = pi_study_match(study_input)  # Find matching PI and study
    except ValueError as e:
        print(f"Error in pi_study_match function: {e}")
        sys.exit(1)  # Exit if no matching PI is found

    # Get the MR scanner type and normalize the input
    scanner = input("Please enter MR Scanner: ").lower().replace(" ", "")
    mrrc_server = "shred.med.yale.edu"
    m_user = "petlab"

    # Load configuration settings, such as petlab password
    config = load_config()
    if config is None:
        m_pswd = getpass("Please enter petlab password: ")  # Prompt for password if config is not found
    else:
        m_pswd = config.get('petlab_password')  # Retrieve password from config file

    client = ssh_connect(mrrc_server, m_user, m_pswd)  # Establish SSH connection

    try:
        # Search for scans related to the PI and scanner
        cmd = f'/home/rtc29/codes/FindMyStudy {scanner} {pi} | grep -i "{scanner}_[[:alnum:]]*_[[:alnum:]]*"'
        scans_list = ssh_command(client, cmd)

        if not scans_list:
            print(f"No scans found for {pi} on {scanner}")
            sys.exit(1)

        # List available scans and prompt the user to select one
        print(f"Found these scans for PI: {pi}")
        print("Enter the number of the scan you'd like to transfer:")
        for i, scan in enumerate(scans_list, start=0):
            print(f"{i} ---> {scan.split()[0]} | {scan.split()[4]}")

        # Get user's scan selection
        scan_index = int(input())
        scan_to_transfer = scans_list[scan_index].split()[0]
        mr_date = scan_to_transfer.split("_")[1]
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

    try:
        # Get the full file path of the selected scan
        cmd = f'readlink -f /data1/{scanner}_transfer/{scan_to_transfer}'
        mr_file_path = ssh_command(client, cmd)[0].rstrip()
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

    client.close()  # Close the SSH client connection

    # Ensure the destination directory for transfer exists
    while True:
        if not study.endswith("_mr"):
            study = (f"{study}_mr")
        pet_dir = Path(f"/data8/data/{study}/{mr_date}_{subject}/3d_dicom")
        if pet_dir.exists():
            file_count = len(list(pet_dir.glob("[MS]R*")))  # Check how many MR files exist
            if file_count > 1:
                if ask_confirmation(f"{pet_dir} exists and contains {file_count} MR files, would you like to continue anyways? (y/n) "):
                    break
                else:
                    print("Not continuing")
                    sys.exit(0)
        else:
            if ask_confirmation(f"Transfer location is set to: {pet_dir}, is this correct? (y/n) "):
                try:
                    pet_dir.mkdir(parents=True, exist_ok=True)  # Create the directory if it doesn't exist
                    break
                except Exception as e:
                    print(f"Error occurred: {e}")
                    sys.exit(1)
            else:
                # Allow user to modify study, MR date, or subject if the location is not correct
                study = input(f"Please enter the correct study name (current: {study}) or press Enter to keep it: ") or study
                mr_date = input(f"Please enter the correct MR date (current: {mr_date}) or press Enter to keep it: ") or mr_date
                subject = input(f"Please enter the correct subject ID (current: {subject}) or press Enter to keep it: ") or subject
    try:
        # Start the transfer using rsync
        print(f"Initiating transfer of {scan_to_transfer} to {pet_dir}")
        subprocess.run(["rsync", "-aW", "--info=progress2", f"{m_user}@{mrrc_server}:{mr_file_path}/*", str(pet_dir)])
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()  # Call the main function to start the program
