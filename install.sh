#!/bin/bash
# Install Sputnik dependencies and python environment
# Run from the root of the Sputnik repo

PYTHONDIR="$PWD/.sputnik-env"

install_packages()
{
    PKGLIST="virtualenv python3 ffmpeg tesseract-ocr"
    sudo apt update

    sudo apt install -y ${PKGLIST}
}

create_virtualenv()
{
    virtualenv -p python3 ${PYTHONDIR}

    ${PYTHONDIR}/bin/pip install -r requirements.txt
}

install_packages
create_virtualenv