import autogen
from typing import Dict, List
from autogen import Agent
import os
import logging
from typing import List, Tuple
import argparse
#logging.basicConfig(level=logging.DEBUG)

web_user_query_template = """
User Query: 
USER_QUERY_HERE

"""
web_index_name_template = """
Index name:
INDEX_NAME_HERE
"""

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

# humans proxy agents
user_proxy = autogen.UserProxyAgent(
    name="Admin",
    system_message="A human admin. Interact with the planner to discuss the plan. Plan execution needs to be approved by admin if human_input_mode is enabled.",
    code_execution_config=False, 
    human_input_mode="ALWAYS", # Always take human input to validate the safety of the plan
    is_termination_msg=termination_msg,
)

executor = autogen.UserProxyAgent(
    name="Executor",
    system_message="Executor. Execute the code written by the Engineer agent and report the result.",
    human_input_mode="ALWAYS",  # Always take human input to validate the safety of the the code being executed.
    code_execution_config={
        "last_n_messages": 3,
        "work_dir": "groupchat",
        "use_docker": False,
    },
    is_termination_msg=termination_msg,
)

# agents
planner = autogen.AssistantAgent(
    name="Planner",
    system_message='''Planner. Once you receive the task from Admin agent, you should response and classify whether this task is belong to OT data query and analysis, or belong to document search and retrieval. 
    If the task is to ask for OT data(like temperature, pressure, etc) information or analysis of OT data, and it needs to be queried from database, classify this task to be OT data query and analysis task. In this case, suggest a plan for Engineer agent to use function call with a given function, and pass the parmeter to the function to query OT data from local InfluxDB. 
    If the task is to ask for content information, document search and retrieval, then classify this task to be document search and retrieval task. In this case, abstract (1) the content that the user want to search and get, as the user_query (2) the index name the user want to search from, as the index_name. Provide the user query and index name contents to the Engineer agent to send them as the inputs to RAG module by calling HTTP request with backend_url, and get 'request_id' value from the http response. You must execute this HTTP call to get 'request_id' first.
    After you get 'request_id' successfully by executing above request, you need to get the result by checking the response periodically with http call check_url. If 'status' in the response is 'success', get 'processed_result' value from the response as the final search result we need. Otherwise you need to continue to call the function periodically with number_of_check and check_interval_second parameters, until number_of_check is reached, or until you can get 'processed_result' result.
    backend_url = 'http://rag-interface-service:8701/webpublish'
    check_url = f'http://rag-interface-service:8701/check_processed_result/{request_id}'
    number_of_check = 60
    check_interval_second = 1
    existing_index_names_url = 'http://rag-vdb-service:8602/list_index_names' #You can validate if index_name is valid by checking it exists in http response 'index_names' of existing_index_names_url. 
    
    Your plan should ask Critic agent to use the retrieved content to answer user query, rephrase retrieved content and make the final answer readable and well address user's question.

    Explain the plan first. You don't write code.
    ''',
    llm_config=agent_config,
)

engineer = autogen.AssistantAgent(
    name="Engineer",
    system_message='''Engineer. You wait until the Planner agent assigns you the plan of the task. You follow an approved plan. Then You call the given python function query_influxdb to solve tasks.
    
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

@executor.register_for_execution()
@engineer.register_for_llm(description="query OT data from local influxDB")
def query_influxdb(date: str) -> Tuple[str, List[str]]:
    from influxdb_client import InfluxDBClient
    # InfluxDB parameters
    url = 'http://influxdb:8086'
    token = 'secret-token'
    org = 'InfluxData'
    bucket = 'manufacturing'
    success_str = ""
    retrieved_data = []
    
    # Create InfluxDB client
    client = InfluxDBClient(url=url, token=token, org=org)
    # Construct InfluxDB query
    query = f'from(bucket: "{bucket}") |> range(start: {date}T00:00:00Z, stop: {date}T23:59:59Z)'
    # Execute the query
    result = client.query_api().query(org=org, query=query)
    
    # Print the queried data
    if result != None:
        success_str = "execution succeeded"
        for table in result:
            for record in table.records:
                retrieved_data.append(f'Time: {record.get_time()}, Value: {record.get_value()}')
    else:
        success_str = "execution failed"
    
    return success_str, retrieved_data


def custom_speaker_selection_func(last_speaker: Agent, groupchat: autogen.GroupChat):
    """Define a customized speaker selection function.
    A recommended way is to define a transition for each speaker in the groupchat.
    Returns:
        Return an `Agent` class or a string from ['auto', 'manual', 'random', 'round_robin'] to select a default method to use.
    """
    messages = groupchat.messages

    if len(messages) <= 1:
        # make sure planner talk first to provide initial plan
        return planner
    if "```python" not in messages[-1]["content"] and 'successfully' in messages[-1]["content"]:
        # critic to terminate
        return critic

    if last_speaker is planner:
        # Always let the user to review after the planner
        return user_proxy
        
    elif last_speaker is user_proxy:
        if "approve" in messages[-1]["content"] or len(messages[-1]["content"]) == 0:
            return engineer
        else:
            return planner

    elif last_speaker is engineer:
        if "```python" in messages[-1]["content"] or len(messages[-1]["content"]) == 0:
            return executor
        elif 'completed' in messages[-1]["content"] or 'successfully' in messages[-1]["content"]:
            return critic
        else:
            return engineer

    elif last_speaker is executor:
        if "exitcode: 1" in messages[-1]["content"] or 'execution succeeded' not in messages[-1]["content"]:
            return engineer
        else:
            return critic

    elif last_speaker is critic:
        if "TERMINATE" not in messages[-1]["content"]:
            return critic 
    else:
        return "auto" # default is auto that use llm to select the next speaker
     
def start_chat(agent_config,web_user_query):
    # start the "group chat" between agents and humans
    groupchat = autogen.GroupChat(agents=[user_proxy, executor, engineer, planner, critic], messages=[], max_round=30, speaker_selection_method=custom_speaker_selection_func,) 
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config = agent_config)

    # Start the Chat!
    chat_result = user_proxy.initiate_chat(
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
    parser = argparse.ArgumentParser(description='Process some query.')
    parser.add_argument('--query', type=str, required=True, help='The query to process')
    args = parser.parse_args()
 
    start_chat(agent_config, args.query)
