## Overview
Configure the GPT model and Phi3 model in the main.py as below.

```python
config_gpt_list = [
    {
        "model": "<azure-openai-model-deployment-name>", 
        "base_url": "<azure-openai-model-url>", 
        "api_type": "azure",
        "api_key": "<azure-openai-model-api-key>", 
        "api_version": "2023-05-15"
    }
]

config_local_llm_list = [
    {
        "model": "phi3-mini", 
        "base_url": "http://<local-model-openai-compatible-api-address>:<port>/v1", 
        "api_type": "open_ai",
        "api_key": "sk-111111111111111111111111111111111111111111111111", # just a placeholder, no need to change.
    }
]
```

Check your `local-model-openai-compatible-api-address` by running the following command after you deployed local-llm-server module to the Kubernetes cluster:
```bash
kubectl logs <local-llm-server-pod-name> -n <namespace>
```