import autogen
from typing import Dict, List
from autogen import Agent
from flask import Flask, request, jsonify
import os
import logging
#logging.basicConfig(level=logging.DEBUG)

web_user_query_template = """
User Query: 
USER_QUERY_HERE

"""
web_index_name_template = """
Index name:
INDEX_NAME_HERE
"""

app = Flask(__name__)
app_port = os.getenv('AGENT_PORT', '8801')

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

# set a "universal" config for the agents
agent_gpt_config = {
    "seed": 42,  # change the seed for different trials
    "temperature": 0,
    "config_list": config_gpt_list,
    "timeout": 600,
}
agent_local_llm_config = {
    "seed": 42,  # change the seed for different trials
    "temperature": 0,
    "config_list": config_local_llm_list,
    "timeout": 600,
}

agent_config = agent_gpt_config

def termination_msg(x):
    return isinstance(x, dict) and "TERMINATE" == str(x.get("content", ""))[-9:].upper()

# proxy agents
user_proxy = autogen.UserProxyAgent(
    name="Admin",
    system_message="A human admin. Interact with the planner to discuss the plan. Plan execution needs to be approved by this admin if human_input_mode is enabled.",
    code_execution_config=False, 
    human_input_mode="NEVER",
    max_consecutive_auto_reply=3, 
    is_termination_msg=termination_msg,
)

executor = autogen.UserProxyAgent(
    name="Executor",
    system_message="Executor. Execute the code written by the Engineer agent and report the result.",
    human_input_mode="NEVER",
    code_execution_config={
        "last_n_messages": 3,
        "work_dir": "groupchat",
        "use_docker": False,
    },
    max_consecutive_auto_reply=3, 
    is_termination_msg=termination_msg,
)

# agents
planner = autogen.AssistantAgent(
    name="Planner",
    system_message='''Planner. Once you receive the task from Admin agent, you should response and classify whether this task is belong to OT data query and analysis, or belong to document search and retrieval. 
    If the task is to ask for OT data(like temperature, pressure, etc) information or analysis of OT data, and it needs to be queried from database, classify this task to be OT data query and analysis task. In this case, suggest a plan for Engineer agent to write a code to query OT data from local InfluxDB. 
    Make sure influxdb-client package is installed in your environment and use influxdb_client to create InfluxDB client to query data. The data contains time and value, print the queried data out for the Critic agent to give further analysis. Create influxDB command with below parameters:
    url = 'http://influxdb:8086'
    token = 'secret-token'
    org = 'InfluxData'
    bucket = 'manufacturing'

    If the task is to ask for content information, document search and retrieval, then classify this task to be document search and retrieval task. In this case, abstract (1) the content that the user want to search and get, as the user_query (2) the index name the user want to search from, as the index_name. Provide the user query and index name contents to the Engineer agent to send them as the inputs to RAG module by calling HTTP request with backend_url, and get 'request_id' value from the http response. You must execute this HTTP call to get 'request_id' first.
    After you get 'request_id' successfully by executing above request, you need to get the result by checking the response periodically with http call check_url. If 'status' in the response is 'success', get 'processed_result' value from the response as the final search result we need. Otherwise you need to continue to call the function periodically with number_of_check and check_interval_second parameters, until number_of_check is reached, or until you can get 'processed_result' result.
    backend_url = 'http://rag-interface-service:8701/webpublish'
    check_url = f'http://rag-interface-service:8701/check_processed_result/{request_id}'
    number_of_check = 300
    check_interval_second = 1
    existing_index_names_url = 'http://rag-vdb-service:8602/list_index_names' #You can validate if index_name is valid by checking it exists in http response 'index_names' of existing_index_names_url. 
    
    Your plan should ask Critic agent to use the retrieved content to answer user query, rephrase retrieved content and make the final answer readable and well address user's question.
    Explain the plan first. You don't write code.
    ''',
    llm_config=agent_config,
)

engineer = autogen.AssistantAgent(
    name="Engineer",
    system_message='''Engineer. You wait until the Planner agent assigns you the plan of the task. You follow an approved plan. Then You write python/shell code to solve tasks.
    For the OT data query and analysis task, install influxdb-client package in your environment and use influxdb_client to create InfluxDB client to query data. The data contains time and value, print the queried data out for the Critic agent to give further analysis. Create influxDB command with below parameters:
    url = 'http://influxdb:8086'
    token = 'secret-token'
    org = 'InfluxData'
    bucket = 'manufacturing'
    
    If the task is for document search and retrieval, use the actual value of user_query and index_name from planner agent as the inputs to backend_url, generate code with below parameters if necessary:
    backend_url = 'http://rag-interface-service:8701/webpublish'
    check_url = f'http://rag-interface-service:8701/check_processed_result/{request_id}'
    number_of_check = 300
    check_interval_second = 1
    existing_index_names_url = 'http://rag-vdb-service:8602/list_index_names' #You can validate if index_name is valid by checking it exists in http response 'index_names' of existing_index_names_url. 
    
    Wrap the code in a code block that specifies the script type. The user can't modify your code. So do not suggest incomplete code which requires others to modify. Don't use a code block if it's not intended to be executed by the executor.
    Don't include multiple code blocks in one response. Do not ask others to copy and paste the result. Check the execution result returned by the executor.
    If the result indicates there is an error, fix the error and output the code again. Suggest the full code instead of partial code or code changes. If the error can't be fixed or if the task is not solved even after the code is executed successfully, analyze the problem, revisit your assumption, collect additional info you need, and think of a different approach to try.
    ''',
    llm_config=agent_config,
)

critic = autogen.AssistantAgent(
    name="Critic",
    system_message='''Critic.  
    For document search and retrieval task, you need to rephrase again the retrieved content from the Executor agent. Make the final answer readable and well addressing the user's query with the retrieved contents. Use the retrieved content from Executor to answer user query of the 1st message in the chat (use the full sentence of the question, for example, the full question like 'How should I fix this machine issue?'). 
    For OT data query and analysis task, you need to wrap the answer for the query result.
    Double check plan, claims, code from other agents and provide feedback.
    You must Reply only 'TERMINATE' to the chat if the task is done or output looks good.
    ''',
    llm_config=agent_config,
)

def custom_speaker_selection_func(last_speaker: Agent, groupchat: autogen.GroupChat):
    """Define a customized speaker selection function.
    A recommended way is to define a transition for each speaker in the groupchat.
    Returns:
        Return an `Agent` class or a string from ['auto', 'manual', 'random', 'round_robin'] to select a default method to use.
    """
    messages = groupchat.messages

    if len(messages) <= 1:
        return planner
    if len(messages) <= 3 and last_speaker is planner:
        return engineer
    if "```python" not in messages[-1]["content"] and 'successfully' in messages[-1]["content"]:
        # critic to terminate
        return critic

    if last_speaker is engineer:
        if "```python" in messages[-1]["content"]:
            # If the last message is a python code block, let the executor to speak
            return executor
        elif 'completed' in messages[-1]["content"] or 'successfully' in messages[-1]["content"]:
            # If task completed, let critic to summarize
            return critic
        else:
            # Otherwise, let the engineer to continue
            return engineer

    elif last_speaker is executor:
        if "exitcode: 1" in messages[-1]["content"] or 'execution succeeded' not in messages[-1]["content"]:
            # If the last message indicates an error, let the engineer to improve the code
            return engineer
        else:
            # Otherwise, let the critic to speak and rephrase the result
            return critic

    elif last_speaker is critic:
       # Always let the user to speak after the critic, to end the conversation
       if "TERMINATE" not in messages[-1]["content"]:
           return critic 
    
    else:
        return "random" # or default "auto"

# Receive user input from the web app
@app.route('/webquery', methods=['POST'])
def publish():
    global agent_config
    data = request.json
    user_query = data.get('user_query')
    index_name = data.get('index_name')
    selected_model = data.get('selected_model')
    logging.info('received data: ', user_query, index_name, selected_model)
    if user_query:
        web_user_query = web_user_query_template.replace('USER_QUERY_HERE',user_query)
        if index_name != 'NA':
            web_index_name = web_index_name_template.replace('INDEX_NAME_HERE',index_name)
            # concatenate the web_user_query with web_index_name
            web_user_query = web_user_query + web_index_name
        
        if selected_model == "phi3-mini":
            agent_config = agent_local_llm_config
        else:
            agent_config = agent_gpt_config
        chat_result = start_chat(agent_config, web_user_query)
       
        return jsonify({'status': 'success', 'message': 'User input sent to agents', 'chat_result': chat_result})
    return jsonify({'status': 'error', 'message': 'Invalid user input'})


def start_chat(agent_config,web_user_query):
    # start the "group chat" between agents and humans
    groupchat = autogen.GroupChat(agents=[user_proxy, executor, engineer, planner, critic], messages=[], max_round=30, speaker_selection_method=custom_speaker_selection_func,)
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config = agent_config)

    # Start the Chat!
    user_proxy.initiate_chat(
        manager,
        message=web_user_query,
    )

    # retrieve final result from the chat log
    chat_log = []
    messages = manager.chat_messages[critic]
    for i in range(len(messages)):
        if messages[i]["name"] == 'Critic':
            chat_log.append(messages[i]['content'])
    if len(chat_log)>0:
        if chat_log[-1] == 'TERMINATE' and len(chat_log)>1:
            return chat_log[-2]
        else: 
            return chat_log[-1]
    else:
        return 'No result'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app_port)
