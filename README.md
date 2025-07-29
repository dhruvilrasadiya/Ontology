# Ontology Building

> **Note:** The following steps only work on Linux Operating Systems.

## Prerequisites

- Docker
- Python 3
- Ollama
- Kafka with the topics:
  - `panini-ontology-request`
  - `panini-ontology-response`

---

## Installation and Setup

### Install Docker

```bash
sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
apt-cache policy docker-ce
sudo apt install docker-ce
sudo systemctl status docker
```

### Create PostgreSQL Container

```bash
sudo docker run --name SET_YOUR_CONTAINER_NAME \
  -e POSTGRES_USER=SET_YOUR_USERNAME \
  -e POSTGRES_PASSWORD=SET_YOUR_PASSWORD \
  -e POSTGRES_DB=SET_YOUR_DATABASE_NAME \
  -p 6024:5432 -d pgvector/pgvector:pg16
```

> Change the port number if required.

### Start and Access the Container

```bash
sudo docker start YOUR_CONTAINER_NAME
sudo docker ps
sudo docker exec -it YOUR_CONTAINER_NAME bash
```

### Activate PostgreSQL Database

```bash
psql -U YOUR_USERNAME -d YOUR_DATABASE
```

### Create Root Directory and Virtual Environment

```bash
mkdir ontology_project
cd ontology_project
python3 -m venv .venv
source .venv/bin/activate
```

### Configure `env.py`

```python
DATABASE_URL = "postgresql+psycopg://YOUR_USERNAME:YOUR_PASSWORD@localhost:6024/YOUR_DATABASE"
```

> Change the port number if required.

### Install Requirements

```bash
pip install -r requirements.txt
```

### Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Download Embedding Model

```bash
ollama pull nomic-embed-text
```

### Start Bootstrap Server

Start the bootstrap server to build the connection between Confluent Kafka and the system.

### Create Kafka Topics

- `panini-ontology-request`
- `panini-ontology-response`

### Run Ontology API

```bash
uvicorn ontology_api:app --reload
```

### Access API via Swagger UI

Open your browser and visit:

```
http://127.0.0.1:8000/docs
```

You can:
1. Upload textbooks to the database.
2. Retrieve text chunks by a list of chunk_ids.
3. Update the category_id of text chunks using chunk_id and updated category_id.
4. Delete a category by category_id.

### Run Ontology Builder

```bash
python ontology_builder.py
```

---

## Instructions

### Creating a New Category

**Required Fields:**

- category_id
- category_name
- parent_id
- learning_obj
- tenant

> `file_id` should be null while creating the category.

**Topic:** `panini-ontology-request`

**Behavior:**

1. Creates a category with given category_id and category_name.
2. If parent_id is not provided, parent_id will be null.
3. learning_obj will be converted into vector embeddings and stored in the vector DB.
4. For subcategories, parent_id should match the category_id of the parent.

---

### Upload Textbook to Existing Category

**Required Fields:**

- file_id
- category_id
- tenant

> All other fields can be null.

**Topic:** `panini-ontology-request`

**Behavior:**

1. If category exists, uploads textbook to that category.
2. If category does not exist, returns an error.
3. Other fields are ignored.

---

### Create Category and Upload Textbook Together

**Required Fields:**

- file_id
- category_id
- category_name
- parent_id
- learning_obj
- tenant

**Topic:** `panini-ontology-request`

**Behavior:**

1. Creates a new category with the given data.
2. Uploads the file to the newly created category.

---

## References

- Docker Installation: https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-20-04

---
