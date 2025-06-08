# pitchperfectpursuit
Adaptive Training in Flight Simulators with Dynamic Difficulty Adjustment and LLM-generated Feedback

**we need to put the pre n post test scores somewhere here**

## Project summary

## Installing software

- [X-Plane 12](https://store.steampowered.com/app/2014780/XPlane_12/)
	- [X-Plane 12 Global Scenery](https://store.steampowered.com/dlc/2014780/XPlane_12/)
- [XPPython3 (X-Plane plugin)](https://xppython3.readthedocs.io/en/latest/)
- [Conda (environment/package manager)](https://www.anaconda.com/docs/getting-started/miniconda/install "Installing Miniconda")
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

### Copying files into X-Plane

- `gunshot.wav` in `path to be filled in`
- `cockpit_crosshair` in `X-Plane 12\Aircraft\Laminar Research\Cessna 172 SP\plugins\xlua\scripts\cockpit_crosshair`

### Configuring XPPython3

- [Install `pyzmq` package](https://xppython3.readthedocs.io/en/latest/usage/pip.html)

### Configuring `server.py`

- In `server.py`, verify that the paths to the VLC and OBS Studio programs are correct

#### *For LLM Feedback only:* [Getting an LLM API key (Gemini)](https://ai.google.dev/gemini-api/docs/api-key)

1. [Get a Gemini API key in Google AI Studio](https://aistudio.google.com/app/apikey)
2. Paste your API key into the `GOOGLE_API_KEY` constant in `server.py`
	- Though doing the above is easier for testing, it is not secure and you should [set up your API key](https://ai.google.dev/gemini-api/docs/api-key#set-up-api-key) as an environment variable

## Conducting the experiment

### Running the relay server

1. If not already activated, activate the `relay_server` conda environment with `conda activate relay_server`
2. Navigate to the relay server directory
3. Start the program with `python server.py`

### Relay server saves/output [update for DDA]

- In the relay server directory, there will be a `saves` folder containing
	- `values.csv` with a stream of data every 0.3 s from X-Plane
	- `plot.jpg` graph of some of the above variables against time
	- `FLIGHT_DESCRIPTION.mp4` X-Plane recordings
