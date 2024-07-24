import streamlit as st
import logging
import requests

#logging.basicConfig(level=logging.INFO)

CONV_HISTORY_NUM = 10
model_options = ["gpt3.5-turbo", "phi3-mini"]
faq = [
    {
        "question": "How should I ensure the workplace safety? use index 'cc-test2'"
    },
    {
        "question": "Show me the ot data from the database in the last 12 hours."
    }
    # Add more FAQ questions and answers as needed
]

st.title('Multi Agent Application Demo')
col1, col2  = st.columns((7,3)) 

if 'conversation_history' not in st.session_state:
	st.session_state.conversation_history = []

def publish_user_input(user_input_json):
    backend_url = 'http://multi-agent-agents-service:8801/webquery'
    try:
        response = requests.post(backend_url, json=user_input_json)
        if response.status_code == 200:
            st.success(response.json()['message'])
            chat_result = response.json()['chat_result']
            # Display assistant response in chat message container
            with col1.chat_message("assistant"):
                col1.write(chat_result)
            # Add assistant response to chat history
            st.session_state.conversation_history.append({"role": "assistant", "content": chat_result})
            # keep the conversation history to a certain number
            if len(st.session_state.conversation_history)> CONV_HISTORY_NUM:
                st.session_state.conversation_history.pop(0) 
        else:
            st.error('Failed to publish user input to the backend')
    except requests.RequestException as e:
        st.error(f'Request failed: {e}')

def query_retrieval():
    with st.sidebar:
        st.title("FAQ")
        for item in faq:
            st.write(f"**question:** {item['question']}")

    with st.spinner(text="Loading..."):
        col1.subheader('Chat history')
        col2.subheader('User configurations')
        # get selected model
        selected_model = col2.selectbox('**Please select the language model:**', model_options, index=0)
        col2.write('You selected:')
        col2.write(selected_model)
        # get the index names from the backend VDB module
        index_names = requests.get('http://rag-vdb-service:8602/list_index_names').json()['index_names']
        index_names.append("NA")
        default_index = index_names.index("NA")
        index_name = col2.selectbox('**Please select an index name:**', index_names, index=default_index)
        # Check if "NA" is selected and set index_name to False if it is
        if index_name != "NA":
            col2.write('You selected:')
            col2.write(index_name)
        else:
            col2.write('No index name selected')

    # Display chat messages from history on app rerun
    for message in st.session_state.conversation_history:
        with col1.chat_message(message["role"]):
            col1.markdown(message["content"])

    prompt = st.chat_input("Please input your question here:")
    if prompt:
        # Display user message in chat message container
        with col1.chat_message("user"):
            col1.markdown(prompt)
        st.session_state.conversation_history.append({"role": "user", "content": prompt})
        
        with st.spinner(text="Document Searching..."):  
            user_input_json = {'user_query': prompt, 'index_name': index_name, 'selected_model': selected_model}
            publish_user_input(user_input_json)
           
if __name__ == "__main__":
    query_retrieval()
