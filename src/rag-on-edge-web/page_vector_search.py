import streamlit as st
import time
import logging
import requests

#logging.basicConfig(level=logging.INFO)

CHECK_INTERVAL_SEC = 1 
CONV_HISTORY_NUM = 5
number_of_check = 300 

retrieval_prompt = '''Use the Content to answer the Search Query.

Search Query: 

SEARCH_QUERY_HERE

Search Content and Answer: 

'''
faq = [
    {
        "persona": "operator",
        "question": "How is the production going?"
    },
    {
        "persona": "operator",
        "question": "Which units have defects and what are the reasons?"
    },
    {
        "persona": "operator",
        "question": "Do we have information on anomalies that might have led to these defects?"
    },
    {
        "persona": "operator",
        "question": "Which machine is causing the defects, and what could be the possible reasons?"
    },
    {
        "persona": "operator",
        "question": "How can we fix this? Are there any guidelines or manuals?"
    }
    # Add more FAQ questions and answers as needed
]


st.title('RAG on Edge Demo')
col1, col2  = st.columns((7,3)) 

if 'conversation_history' not in st.session_state:
	st.session_state.conversation_history = []

def check_processed_result(request_id, user_input_json):
    check_url = f'http://rag-interface-service:8701/check_processed_result/{request_id}'
    response = requests.get(check_url)
    
    if response.status_code == 200:
        result_data = response.json()
        if result_data['status'] == 'success':
            query_response_str = result_data['processed_result']
            # Display assistant response in chat message container
            with col1.chat_message("assistant"):
                col1.write(query_response_str)
            # Add assistant response to chat history
            st.session_state.conversation_history.append({"role": "assistant", "content": query_response_str})
            # keep the conversation history to a certain number
            if len(st.session_state.conversation_history)> CONV_HISTORY_NUM:
                st.session_state.conversation_history.pop(0) 

            return True
    return False

def publish_user_input(user_input_json):
    backend_url = 'http://rag-interface-service:8701/webpublish'
    number_of_check_counter = number_of_check
    try:
        response = requests.post(backend_url, json=user_input_json)
        if response.status_code == 200:
            request_id = response.json()['request_id']
            # Check for processed results periodically
            for _ in range(number_of_check):  
                number_of_check_counter -= 1
                if number_of_check_counter == 0:
                    st.error('Timeout! Failed to get query response. Please try again later.')
                    break
                if check_processed_result(request_id, user_input_json):
                    break
                time.sleep(CHECK_INTERVAL_SEC)
        else:
            st.error('Failed to publish user input to the backend')
    except requests.RequestException as e:
        st.error(f'Request failed: {e}')

def query_retrieval():
    global number_of_check
    with st.sidebar:
        st.title("User Account")
        st.write(f"**name:** user 1")
        st.write(f"**role:** Plant manager")
        st.write(f"**location:** Factory Monterrey")
        st.write(f"Production line: 5")
        st.title("FAQ")
        for item in faq:
            st.write(f"**question:** {item['question']}")

    with st.spinner(text="Loading..."):
        col1.subheader('Chat history')
        col2.subheader('User configurations')
        index_names = requests.get('http://rag-vdb-service:8602/list_index_names').json()['index_names']
        index_name = col2.selectbox('**Please select an index name:**',index_names)
        col2.write('You selected:')
        col2.write(index_name)
        resp_timeout = col2.text_input('**Please input response timeout in seconds (default 300s):**', 300)
        number_of_check = int(resp_timeout) if resp_timeout else 300

    # Display chat messages from history on app rerun
    for message in st.session_state.conversation_history:
        with col1.chat_message(message["role"]):
            col1.markdown(message["content"])

    prompt = st.chat_input("Please input your question here:")
    if prompt and index_name:
        # Display user message in chat message container
        with col1.chat_message("user"):
            col1.markdown(prompt)
        st.session_state.conversation_history.append({"role": "user", "content": prompt})
        
        with st.spinner(text="Document Searching..."):  
            retrieval_prepped = retrieval_prompt.replace('SEARCH_QUERY_HERE',prompt)

            user_input_json = {'user_query': prompt, 'index_name': index_name}
            publish_user_input(user_input_json)
           

if __name__ == "__main__":
    query_retrieval()

