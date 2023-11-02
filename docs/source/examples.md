# Experiment examples

Here we will present several examples of using netunicorn platform for network-oriented data collection purposes, including experiment descriptions and links to the code.

## Deployment of netunicorn
For all these experiments, we assume that you have access to netunicorn deployment operating within some infrastructure. If yes, skip this section and proceed to the next one.

If this is not the case and you want to explore these experiments on your own, we suggest to easily deploy your own test copy of netunicorn based on Docker compose file.

### Prerequisites
- Linux-based OS (as Docker containers are Linux-based)
- Installed `wget`
- Installed Docker and Docker Compose plugin. Please, refer to [Docker installation guide](https://docs.docker.com/engine/install/) and [Docker Compose installation guide](https://docs.docker.com/compose/install/).
    - If you use rootless installation of Docker, please modify `/var/run/docker.sock` links on the left side of volume sections in docker-compose.yml file as needed (usually, to `/run/user/1000/docker.sock` if your user id is 1000)

### Installation

1. Create a separate folder for local netunicorn configuration files and `cd` into this folder.
2. Download and run installation script:
   ```bash
   wget https://raw.githubusercontent.com/netunicorn/netunicorn/main/netunicorn-director/scripts/install.sh
   chmod +x install.sh
   ./install.sh
   ```
   - This script will create needed directories and put configuration files into them.
   - **Optional:** We encourage you to explore the file content before running to verify the harmless nature of the script.
3. Run docker compose:
   ```bash
   docker compose up
   ```
   - This command will download and run all needed containers.
   - **Optional:** You can explore the `docker-compose.yml` file content before running and make changes as needed.

Now you should have running instance of `netunicorn` platform on your machine.

## Preparation
You should have the following information to interact with netunicorn platform:
- NETUNICORN_ENDPOINT: URL of netunicorn API endpoint. Provided by installation administrator. If you use local installation deployed from `docker-compose.yml` file, it would be the endpoint of `mediator` service in `docker-compose.yml` file (by default: `http://localhost:26611`)
- NETUNICORN_LOGIN: login of your user account. Provided by installation administrator. If you use local installation deployed from `docker-compose.yml` file, it would be `test` (you can change it in `development/users.sql` file before running `docker compose`).
- NETUNICORN_PASSWORD: password of your user account. Provided by installation administrator. If you use local installation deployed from `docker-compose.yml` file, it would be `test` (provided as `bcrypt2`-hashed value in `development/users.sql` file).

We propose to store these values in environment variables for convenience. For example, for local installation, you can run the following commands in the same terminal session where you will use netunicorn client or run jupyter-notebook:
```bash
export NETUNICORN_ENDPOINT=http://localhost:26611
export NETUNICORN_LOGIN=test
export NETUNICORN_PASSWORD=test
```

All experiments are implemented as Jupyter notebooks. You can find them in [examples](https://github.com/netunicorn/netunicorn/tree/main/examples) folder of netunicorn repository.


## Basic Sleep Experiment

### Goal
Verify the basic functionality of netunicorn platform and check the correctness of the data collection process.

### Experiment Design
This experiment verifies if netunicorn installation is working correctly and accessible by the user. Specifically, it:
1. Verifies installation of needed Python packages, connection to netunicorn API endpoint and user authentication.
2. Describes how to create a simple pipeline consisting of several `sleep` tasks.
3. Describes how to use `nodes` objects to get information about the nodes in the infrastructure.
4. Leads through the process of running the experiment and obtaining the results.

### Result
As a result, you should be able to learn the basics of netunicorn platform and run your first experiment.

### Jupyter Notebook
[https://github.com/netunicorn/netunicorn/blob/main/examples/basic_example.ipynb](https://github.com/netunicorn/netunicorn/blob/main/examples/basic_example.ipynb)

## Speed Test Experiment

### Goal
Collect network performance metrics from multiple nodes in the infrastructure using speed-test utility and store the resulting PCAP files for future analysis.

### Experiment Flow
This experiment shows an example of real-world data collection from a complex infrastructure. In particular, it:
1. Starts the network traffic capturing on the experiment nodes.
2. Execute Ookla Speed Test on these nodes
3. Saves the resulting traffic and uploads it to the cloud storage.
4. Demonstrates the result of execution, how to parse and read them.

### Result
As a result, you should have results of speed-test measurements and corresponding PCAP files for future analysis using your favorite tools and methods.

### Jupyter Notebook
[https://github.com/netunicorn/netunicorn/blob/main/examples/speed_test_example.ipynb](https://github.com/netunicorn/netunicorn/blob/main/examples/speed_test_example.ipynb)

## Video Data Collection Experiment

### Goal
In this experiment, we will watch videos from various platforms and record the corresponding network traffic for future analysis.

### Experiment Flow
This example shows how nodes could interact with various video streaming platforms, in particular YouTube, Vimeo, and Twitch. We will watch videos (or streams) from them and record the network traffic. Specifically, this experiment:
1. Creates the pipeline with watching YouTube, Vimeo, and Twitch, while recording network traffic.
2. Demonstrates the principle of environment_definition object, how environment preparation commands are stored inside, and how to use your own Docker image for the experiment.
3. Executes the pipeline on the nodes from an infrastructure and uploads the resulting data to cloud data storage platform.

### Result
As a result, you should have YouTube, Vimeo, and Twitch video streaming network recording that you can later analyse and explore.

### Jupyter Notebook
[https://github.com/netunicorn/netunicorn/blob/main/examples/video_watchers_example.ipynb](https://github.com/netunicorn/netunicorn/blob/main/examples/video_watchers_example.ipynb)
