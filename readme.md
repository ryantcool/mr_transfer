# Python Executable to Transfer MRI's between MRRC and PET Server

*Please keep in mind this is a work-in-progress*

## Building the images
- Clone repo
    - `git clone https://codeberg.org/ryantcool/mr_transfer.git && cd mr_transfer`

- Create images from Dockerfile
    - `docker build -f Dockerfile.rocky -t rocky_image .`

- Run/Start the container
    - `docker run -it --name rocky_container -d -v $(pwd):/code rocky_image`

## After building and running
- Enter container via docker cli
    - `docker exec -it rocky_container /bin/bash`
- Create a python venv and activate it
    - `python3 -m venv .venv`
    - `source .venv/bin/activate`
- Install packages from **requirements.txt**
    - `python3 -m pip install -r requirements.txt`
    
## Creating the executable via pyinstaller
- With the venv activated and all the packages installed from **requirements.txt** 
    - `pyinstaller /code/src/main.py --name mr_transfer --onefile`
- Binaries will be created in **dist** folder