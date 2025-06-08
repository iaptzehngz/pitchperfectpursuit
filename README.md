# pitchperfectpursuit
Adaptive Training in Flight Simulators with Dynamic Difficulty Adjustment and LLM-generated Feedback

## Project summary

## Installing software & content

- [X-Plane 12](https://store.steampowered.com/app/2014780/XPlane_12/)
	- [X-Plane 12 Global Scenery](https://store.steampowered.com/dlc/2014780/XPlane_12/)
- [XPPython3 (X-Plane plugin)](https://xppython3.readthedocs.io/en/latest/)
- [Conda package manager](https://www.anaconda.com/docs/getting-started/miniconda/install "Installing Miniconda")
- [OBS Studio](https://obsproject.com/download)
- [VLC Media Player](https://www.videolan.org/vlc/index.html)

## Configuring programs

### Creating and activating Python environment for `server.py`

[Set up environment for relay server](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-from-an-environment-yml-file "creating environment from environment.yml file"):
1. Create the environment from the `environment.yml` file found in the wanted `Server` folder:
	1. [Start conda](https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html#starting-conda)
	2. Navigate to the relay server directory with `cd PATH_TO_RELAY_SERVER_DIRECTORY`
	3. Run `conda env create -f environment.yml`
2. Activate the new environment:
	1. Run `conda activate relay_server`

### Setting up OBS

1. [Add sources to your scenes](https://obsproject.com/kb/quick-start-guide)
2. [Enable websocket server](https://obsproject.com/kb/remote-control-guide)
	1. Navigate to Tools > WebSocket Server Settings
  2. Check the "Enable WebSockets server" box

### Configuring `server.py`/XPPython3

- In `server.py`, verify that the paths to the VLC and OBS Studio program are correct
- **Refer to DDA/README.md or LLM Feedback/README.md for additional instructions/setup unique to each trial/mode of adaptive training**

### Copying files into X-Plane

- `gunshot.wav` in `path to be filled in`
- `cockpit_crosshair` in `X-Plane 12\Aircraft\Laminar Research\Cessna 172 SP\plugins\xlua\scripts\cockpit_crosshair`

## Conducting the experiment

### Running the relay server

1. If not already activated, activate the `relay_server` conda environment with `conda activate relay_server`
2. Navigate to the relay server directory
3. Start the program with `python server.py`

### Saves folders

- Videos will be saved to `Server/saves`
