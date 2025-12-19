#!/usr/bin/env python3

import subprocess
import sys
from getpass import getpass
from pathlib import Path

from paramiko import AuthenticationException, AutoAddPolicy, SSHClient

pi_dict = {
    "cosgrove": [
        "bava_ptsd_aud",
        "fmozat_dex",
        "mukappa_aud",
        "pbr_app311_aud",
        "pbr_oud",
    ],
    "davis": ["ekap_ptsd", "fpeb_bpd", "pbr_ed"],
    "esterlis": [
        "app311_fpeb",
        "app311_ket",
        "fpeb_abp_mdd",
        "sdm8_sdc",
        "sv2a_aging_mdd",
    ],
    "zakiniaeiz": ["flb_aud"],
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
    if study.lower() == "bypass":
        print("Bypassing pi_dict lookup...")
        study = input("Manually set study name: ")
        pi_name = input("Manually enter PI: ")
        return pi_name, study
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


def ask_confirmation(
    prompt, input_method=input, negative_action=None, negative_message=""
):
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


def ssh_connect(host, usr):
    """
    Establish an SSH connection to a remote host.

    Args:
        host (str): The hostname or IP address of the remote server.
        usr (str): The username for authentication.

    Returns:
        SSHClient: An SSH client instance connected to the remote host.

    Raises:
        AuthenticationException: If authentication fails.
        Exception: For other connection issues.
    """
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    while True:
        pswd = getpass(f"Please enter {usr} password: ")
        try:
            # Attempt to connect using provided credentials
            client.connect(hostname=host, username=usr, password=pswd, timeout=2)
            break
        except AuthenticationException:
            print("Authentication failed. Please try again.")
        except TimeoutError:
            print("Connection timed out. Try again.")
        except Exception as e:
            print(f"Connection error: {e}")
            retry = input("Would you care to try again? (y/n)").strip().lower()
            if retry != "y":
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
            print(
                f"Error occurred during execution:\n{''.join(stderr_output)}",
                file=sys.stderr,
            )

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

    client = ssh_connect(mrrc_server, m_user)  # Establish SSH connection

    try:
        # Search for scans related to the PI and scanner
        cmd = f'/home/rtc29/Documents/codes/FindMyStudy.sh {scanner} {pi} | grep -i "{scanner}_[[:alnum:]]*_[[:alnum:]]*"'
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
        cmd = f"readlink -f /data1/{scanner}_transfer/{scan_to_transfer}"
        mr_file_path = ssh_command(client, cmd)[0].rstrip()
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

    client.close()  # Close the SSH client connection

    # Ensure the destination directory for transfer exists
    while True:
        if not study.endswith("_mr"):
            study = f"{study}_mr"
        pet_dir = Path(f"/data8/data/{study}/{mr_date}_{subject}/3d_dicom")
        if pet_dir.exists():
            file_count = len(
                list(pet_dir.glob("[MS]R*"))
            )  # Check how many MR files exist
            if file_count > 1:
                if ask_confirmation(
                    f"{pet_dir} exists and contains {file_count} MR files, would you like to continue anyways? (y/n) "
                ):
                    break
                else:
                    print("Not continuing")
                    sys.exit(0)
        else:
            if ask_confirmation(
                f"Transfer location is set to: {pet_dir}, is this correct? (y/n) "
            ):
                try:
                    pet_dir.mkdir(
                        parents=True, exist_ok=True
                    )  # Create the directory if it doesn't exist
                    break
                except Exception as e:
                    print(f"Error occurred: {e}")
                    sys.exit(1)
            else:
                # Allow user to modify study, MR date, or subject if the location is not correct
                study = (
                    input(
                        f"Please enter the correct study name (current: {study}) or press Enter to keep it: "
                    )
                    or study
                )
                mr_date = (
                    input(
                        f"Please enter the correct MR date (current: {mr_date}) or press Enter to keep it: "
                    )
                    or mr_date
                )
                subject = (
                    input(
                        f"Please enter the correct subject ID (current: {subject}) or press Enter to keep it: "
                    )
                    or subject
                )
    try:
        # Start the transfer using rsync
        print(f"Initiating transfer of {scan_to_transfer} to {pet_dir}")
        subprocess.run(
            [
                "rsync",
                "-aW",
                "--info=progress2",
                "-e",
                "ssh -o HostKeyAlgorithms=ssh-rsa",
                f"{m_user}@{mrrc_server}:{mr_file_path}/*",
                str(pet_dir),
            ]
        )
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()  # Call the main function to start the program
