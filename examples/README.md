# netUnicorn User Examples
In this folder you can find examples of different aspects of usage the netUnicorn platform.
- basic_example.ipynb: general information of how to connect to the platform and run your first experiment
- local_executor.ipynb: information about how to run netunicorn executor locally to debug pipeline execution
- tasks_and_dispatchers.ipynb: information about how to create your own Tasks and TaskDispatchers for the platform
- speed_test_example.ipynb: example how to run experiment for measuring simple speedtest using the netUnicorn
- video_watchers_example.ipynb: example how to run experiment for watching video from different platforms (YouTube, Twitch, Vimeo) using the netUnicorn and custom Docker container
- flags_example.ipynb: example how to run experiments with flags for synchronization of execution of different pipelines in the experiment.

## Jupyter Notebook

Each of these examples is provided as a Jupyter Notebook. To run it, you should install Jupyter Notebook (in addition to `netunicorn-client` and `netunicorn-library` packages) and run it in the folder with the example.

```bash
pip install jupyter
jupyter notebook
```

Jupyter Notebook is an interactive Python environment that allows you to run code in the cells and see the results of its execution. You can read more about Jupyter Notebook [here](https://jupyter.org/).

## Suggested order of reading

We suggest starting with the `basic_example.ipynb` to get familiar with the basic concepts and the platform.

Afterward, `tasks_and_dispatchers.ipynb` and `local_executor.ipynb` will provide you the context on writing your tasks and local execution of your pipeline to verify its correctness.

Later, `speed_test_example.ipynb` and `video_watchers_example.ipynb` provide a real-world examples of experiments and describe how to use other Docker images for your experiment.

Finally, `flags_example.ipynb` describes advanced topics of synchronization of different pipelines in the experiment.