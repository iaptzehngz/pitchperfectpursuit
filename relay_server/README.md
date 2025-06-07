
# Relay Server

## Conda setup

[Ensure conda is set up on your system](https://www.anaconda.com/docs/getting-started/miniconda/install "Installing Miniconda")

## Conda environment setup & activation

[Set up environment for relay server](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-from-an-environment-yml-file "creating environment from environment.yml file"):
1. Create the environment from the `environment.yml` file:
	1. [Start conda](https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html#starting-conda)
	2. Navigate to the relay server directory with `cd PATH_TO_RELAY_SERVER_DIRECTORY`
	3. Run `conda env create -f environment.yml`
2. Activate the new environment:
	1. Run `conda activate relay_server`

## Relay server usage

### [Getting an LLM API key (Gemini)](https://ai.google.dev/gemini-api/docs/api-key)

1. [Get a Gemini API key in Google AI Studio](https://aistudio.google.com/app/apikey)
2. Paste your API key into the `GOOGLE_API_KEY` constant in `server.py`
	- Though doing the above is easier for testing, it is not secure and you should [set up your API key](https://ai.google.dev/gemini-api/docs/api-key#set-up-api-key) as an environment variable

### Running the relay server

1. With the relay_server conda environment activated, navigate to the relay server directory
2. Start the program with `python server.py`

### Relay server saves/output

- In the relay server directory, there will be a `saves` folder containing
	- `values.csv` with a stream of data every 0.3 s from X-Plane
	- `plot.jpg` graph of some of the above variables against time
	- `FLIGHT_DESCRIPTION.mp4` X-Plane recordings
