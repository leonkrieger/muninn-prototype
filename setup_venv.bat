:: Create virtual enviroment
py -m venv .venv

:: Prepare pip
py -m pip install --upgrade pip
py -m pip --version

:: Install requirements
py -m pip install .

echo "Virtual Enviroment setup completed"