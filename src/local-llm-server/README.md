## Overview
This is a LLM server that can be used to run local LLM on edge kubernetes cluster and expose OpenAI-compatible port for agentic application to connect to. 
Download a LLM/SLM model and put into the folder `models/` and run the server.
For using Phi3 mini:

- install lfs.
  Ubuntu:

  ```bash
  apt-get install git-lfs
  git lfs install 
  ```

- download model from [huggingface - phi-3-mini-4k-instruct.Q4_K_M.gguf and config.json](https://huggingface.co/SanctumAI/Phi-3-mini-4k-instruct-GGUF/tree/main) and put both files into the folder `models/phi3-mini`:

  ```bash
  curl -L https://huggingface.co/SanctumAI/Phi-3-mini-4k-instruct-GGUF/resolve/main/phi-3-mini-4k-instruct.Q4_K_M.gguf?download=true --output phi-3-mini-4k-instruct.Q4_K_M.gguf
  ```
