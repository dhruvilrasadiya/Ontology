#  Ontology Building
NOTE: The below steps only works on Linux Operating System.

**Step: 1**
Install docker for creating the database in it.
Open the terminal and write the command for install the docker:
    `sudo apt install apt-transport-https ca-certificates curl software-properties-common`
    `curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -`
    `sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"`
    `apt-cache policy docker-ce`
    `sudo apt install docker-ce`

Check the status of the installation.
    `sudo systemctl status docker`


**Step: 2**
Create the container in the docker.
Command for create the container which can have the postgresql database.
    `sudo docker run --name SET_YOUR_CONTAINER_NAME -e POSTGRES_USER=SET_YOUR_USERNAME -e POSTGRES_PASSWORD=SET_YOUR_PASSWORD -e POSTGRES_DB=SET_YOUR_DATABASE_NAME -p 6024:5432 -d pgvector/pgvector:pg16`
(change the port number if required)


**Step: 3**
Start the container to access the database.
Command for start the container:
    `sudo docker start YOUR_CONTAINER_NAME`
Check the status of the container:
    `sudo docker ps`
Execute the container:
    `sudo docker exec -it YOUR_CONTAINER_NAME bash`


**Step: 4**
Activate the database with the username and database name.
Command for activate the database:
    `psql -U YOUR_USERNAME -d YOUR-DATABASE`


**Step 5** 
Create the root directory in the system to save all source files. 


**Step 6** 
In the root directory, Create a virtual environment 
Open the new terminal and write the command for create virtual emvironment: 
	`python3 -m venv .venv` 


**Step 7** 
Activate that virtual environment 
Command for activate the virtual environment: 
	`source .venv/bin/activate` 


**Step: 8**
Edit the env.py file.
change the connection string according to your database.
    `DATABASE_URL = "postgresql+psycopg://YOUR_USERNAME:YOUR_PASSWORD@localhost:6024/YOUR_DATABASE"`
(change the port number if required)


**Step 9** 
Install all the required libraries and dependencies. 
There is requirements.txt file which contains the list of the required libraris. 
Commad for install libraries: 
	`pip install -r requirements.txt` 


**Step 10** 
Install the ollama for download the embedding model.
Command for install the ollama:
    `curl -fsSL https://ollama.com/install.sh | sh`


**Step 11** 
Download the embedding model from ollama to convert the text into vector embeddings.
Command for download the embedding model
    `ollama pull nomic-embed-text`


**step 12**
Run bootstrap server with your localhost to build the connection betweeen confluent-kafka and system.


**step 13**
Create new topics in confluent-kafka
Name of topics : "panini-ontology-request"
                 "panini-ontology-response"


**Step 14** 
Run the ontology_api.py file for api request.
Open the terminal and write the following command to run the ontology_api.py file.
    `uvicorn ontology_api:app --reload`


**Step 15** 
Uvicorn will run on the localhost.
Paste that host address in the browser.
Localhost address looks like:
    **http://127.0.0.1:8000**
Add */docs* at the end of the localhost address to access the swagger UI.
1. With this URL you can access the API endpoint for upload the textbooks to database.
2. you can access the API endpoint for text chunks on the request of list of chunk_ids.
3. you can accesst the API endpoint for update the category_id of the text chunks by the request of chunk_id and     the updated category_id.
4. you can also access the API endpoint for delete the category by request of category_id.


**Step 16** 
Run ontology_builder.py file for create the category and process the textbooks.
Open the new terminal and run the following command to run the support_queue_processor.py file.
    `python ontology_builder.py`



**Instruction for category creation**
Entities required for creating the category :
    category_id
    Category_name
    parent_id
    learning_obj
    tenant
    (file_id should be null while creating the category)
Topic for request these entities :
    'panini-ontology-request'
1. This request in kafka will create new category with the given category_id and category_name.
2. If parent_id is not provided, then the category will be created with null parent_id.
3. The learning_obj of that category will be convert in vector embeddings and stored in the vector database for similarity search purpose.
4. while you are creating the sub-category for perticular category, the parent_id of the sub-category will be the category_id of that perticular category in which you are creating the sub-category.



**Instruction for upload text-book in already created category**
Entities required for text-book upload in created category :
    file_id
    category_id
    tenant
    (All the remaining entities should be null.)
Topic for request these entities :
    'panini-ontology-request'
1. if the value of that remaining entities are coming in the request, then it will not affect the functionality of uploading the text-book in that perticuler category.
2. It means when the file_id is coming in the request, then it will check if the category is exist or not. if the category is exist, then it will upload the text-book in that category. if the category is not exist, then it will show the error message.



**Instruction for upload text-book while creating new category**
Entities required for creating the category :
    file_id
    category_id
    category_name
    parent_id
    learning_obj
    tenant
Topic for request these entities :
    'panini-ontology-request'
1. This request in kafka will first create the category with the requested category_id and category_name.
2. After creating the category it will take the file_id and upload that file to the newly created category.



**References**
Docker installation
https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04
TODO : update send_response function to send the response in proper format.(Take reference from item module.)
