import streamlit as st
import requests

FUNCTION_URL  = ""

st.title('Deploy Cloud Vector Data to Edge VDB')
st.write('**Please select an existing index name or input an index name with that you want to deploy the data and update the vector content.**')
# Option for the user to select
option = st.radio("Choose an option:", ('Select an existing index name', 'Input an index name'))
if option == 'Select an existing index name':
    with st.spinner(text="Loading..."):
        backend_url = 'http://rag-vdb-service:8602/list_index_names'  
        index_names = requests.get(backend_url).json()['index_names']
        index_name_restore = st.selectbox('Please select an index name.',index_names)
        st.write('You selected:', index_name_restore)

elif option == 'Input an index name':
    # restore backup file to update the local VDB content with the cloud VDB embeddings
    index_name_restore = st.text_input('Input an index name:')
    st.write('You input:', index_name_restore)

st.markdown("<br><br>", unsafe_allow_html=True)  # Adds 1 blank lines

if st.button('Update Index Contents'):
    if index_name_restore == '':
        st.error('Please input index name for updating the vector content!')
        st.stop()
    else:
        with st.spinner('Updating index contents...'):
            update_url = 'http://rag-vdb-service:8602/restore_index_contents_backupfile'  # Replace with your actual backend URL
            payload = {'index_name': index_name_restore}
            response = requests.post(update_url, json=payload)

            if response.status_code == 200:
                st.success(f"{response.json()['message']}")
            else:
                st.error(f"Failed to update index contents. Error: {response.text}")


st.markdown("<br><br><br><br>", unsafe_allow_html=True)  # Adds 3 blank lines
st.write('**For demo of triggering cloud indexing**')
st.write('Below is only for demo of triggering cloud indexing: chunk and vectorize the documents in Azure Blob, and store the vector data into the cloud VectorDB master.')
st.write('The doc pre-stored in Az Blob used for demo: Benefit_Options.pdf')
index_name_cloud = st.text_input('Input an index name to store in the cloud VDB:')
st.write('You input:', index_name_cloud)
if st.button('Cloud Indexing'):
    doc_info_list = [
        {"name": "Benefit_Options.pdf", "url": f"<blob-url-your-doc>", "index": index_name_cloud}
    ]
    for doc_info in doc_info_list:
        doc_name = doc_info["name"]
        doc_url = doc_info["url"]
        index_name = doc_info["index"]
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "doc_name": doc_name,
            "doc_url": doc_url,
            "index_name": index_name
        }
        # Trigger Azure Function
        response = requests.post(FUNCTION_URL, json=payload, headers=headers)
        if response.status_code == 200:
            st.success(f"Azure Function Response: {response.text}")
            print(f"Azure Function Response: {response.text}")
        else:
            st.error(f"Failed to trigger Azure Function: {response.text}")
            print(f"Failed to trigger Azure Function: {response.text}")
