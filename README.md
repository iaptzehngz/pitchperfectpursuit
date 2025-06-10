# pitchperfectpursuit

## Project summary

Adaptive Training in Flight Simulators with Dynamic Difficulty Adjustment and LLM-generated Feedback

## Installing software

- [X-Plane 12](https://store.steampowered.com/app/2014780/XPlane_12/)
	- [X-Plane 12 Global Scenery](https://store.steampowered.com/dlc/2014780/XPlane_12/)
- [XPPython3 (X-Plane plugin)](https://xppython3.readthedocs.io/en/latest/)
- [Conda (environment/package manager)](https://www.anaconda.com/docs/getting-started/miniconda/install "Installing Miniconda")
- [OBS Studio](https://obsproject.com/download)
- [VLC Media Player](https://www.videolan.org/vlc/index.html)

## Configuring programs

### Downloading and moving resources

[Download the required resources](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives#downloading-source-code-archives-from-the-repository-view).

#### Copying files into X-Plane

- `gunshot.wav` in `"X-Plane 12\Resources\sounds\weapons"`
- `cockpit_crosshair` in `"X-Plane 12\Aircraft\Laminar Research\Cessna 172 SP\plugins\xlua\scripts\cockpit_crosshair"`
- For control experiment:
	- `Control/PI_control` in `"X-Plane 12\Resources\plugins\PythonPlugins"`
	- `Control/control.py` in any directory 
- For DDA experiment:
  	- `DDA/PI_DDA` in `"X-Plane 12\Resources\plugins\PythonPlugins"`
  	- `DDA/dda.py` in any directory
- For feedback experiment:
 	- `Feedback/PI_adaFeedback` in `"X-Plane 12\Resources\plugins\PythonPlugins"`
	- `Feedback/feedback.py` in any directory

### Creating and activating Python environment for `server.py`

[Set up environment for relay server](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-from-an-environment-yml-file "creating environment from environment.yml file"):
1. Create the environment with `environment.yml`:
	1. [Start conda](https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html#starting-conda)
	2. Navigate to the relay server directory with [`cd`](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cd)
	3. Run `conda env create -f environment.yml`
2. Activate the new environment:
	1. Run `conda activate relay_server`

### Setting up OBS

1. [Add sources to your scenes](https://obsproject.com/kb/quick-start-guide)
2. [Enable websocket server](https://obsproject.com/kb/remote-control-guide)
	1. Navigate to Tools > WebSocket Server Settings
	2. Check the "Enable WebSockets server" box

### Configuring XPPython3

- [Install `pyzmq` package](https://xppython3.readthedocs.io/en/latest/usage/pip.html)

### Configuring `control.py`, `dda.py` or `feedback.py`

- In the above files, verify that the paths to the [VLC Media Player](https://www.google.com/search?q=path+to+vlc+media+player) and [OBS Studio](https://www.google.com/search?q=path+to+obs+studio) programs are correct

#### *For LLM Feedback only:* [Getting an LLM API key (Gemini)](https://ai.google.dev/gemini-api/docs/api-key)

1. [Get a Gemini API key in Google AI Studio](https://aistudio.google.com/app/apikey)
2. Paste your API key into the `GOOGLE_API_KEY` constant in `server.py`
	- Though doing the above is easier for testing, it is not secure and you should [set up your API key](https://ai.google.dev/gemini-api/docs/api-key#set-up-api-key) as an environment variable
