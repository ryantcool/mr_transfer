#!/usr/bin/env python3.11

import os
import subprocess
from sys import exit
from pathlib import Path
from paramiko import SSHClient, AuthenticationException
from getpass import getpass


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
    """ Get absolute path to resource, works for dev and for PyInstaller """
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
        exit(1)
    except Exception as e:
        print(f"Connection error: {e}")
        exit(1)
    return client


def ssh_command(client, cmd):
    try:
        stdin, stdout, stderr = client.exec_command(cmd)
        return stdout.readlines()
    except Exception as e:
        print(f"SSH command execution error: {e}")
        return []


def main():
    # MRRC Connect
    pi = input("Enter PI's last name: ").lower()
    scanner = input("Enter Scanner: ").lower().replace(" ", "")
    mrrc_server = "shred.med.yale.edu"
    m_user = "petlab"
    m_pswd = getpass("Please enter petlab password: ")
    client = ssh_connect(mrrc_server, m_user, m_pswd)

    try:
        cmd = f'/home/rtc29/codes/FindMyStudy {scanner} {pi} | grep -i "{scanner}_[[:alnum:]]*_[[:alnum:]]*"'
        scans_list = ssh_command(client, cmd)

        if not scans_list:
            print(f"No scans found for {pi} on {scanner}")
            exit(1)

        print("Enter the number of the scan you'd like to transfer:")
        for i, scan in enumerate(scans_list, start=0):
            print(f"{i} ---> {scan.split()[0]} | {scan.split()[4]}")

        scan_index = int(input())
        scan_to_transfer = scans_list[scan_index].split()[0]
        mr_date = scan_to_transfer.split("_")[1]
    except Exception as e:
        print(f"Error occurred: {e}")
        exit(1)

    try:
        cmd = f'readlink -f /data1/{scanner}_transfer/{scan_to_transfer}'
        mr_file_path = ssh_command(client, cmd)[0].rstrip()
    except Exception as e:
        print(f"Error occurred: {e}")
        exit(1)

    client.close()

    # Pet Connect
    while True:
        study = input('Please enter name of PET study: ')
        if not study.endswith("_mr"):
            study = (f"{study}_mr")
        else:
            pass
        subject = input('Please enter subject PET ID: ')
        pet_dir = Path(f"/data8/data/{study}/{mr_date}_{subject}/3d_dicom")
        if pet_dir.exists():
            file_count = len(list(pet_dir.glob("[MS]R*")))
            if file_count > 1:
                if ask_confirmation(f"{pet_dir} exists and contains {file_count} MR files, would you like to continue anyways? (y/n) "):
                    break
                else:
                    print("Not continuing")
                    exit(0)
        else:
            try:
                if ask_confirmation(f"You entered {pet_dir}, is this correct? (y/n) "):
                    pet_dir.mkdir(parents=True, exist_ok=True)
                    break
                else:
                    continue
            except Exception as e:
                print(f"Error occurred: {e}")
                exit(1)

    try:
        print(f"Initiating transfer of {scan_to_transfer} to {pet_dir}")
        subprocess.run(["rsync", "-rvzP", f"{m_user}@{mrrc_server}:{mr_file_path}/*", str(pet_dir)])
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()
