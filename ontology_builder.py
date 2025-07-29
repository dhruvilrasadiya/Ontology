import json
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector
from env import DATABASE_URL
from confluent_kafka import Consumer, Producer
from langchain_core.documents import Document
from sqlalchemy import create_engine, Column, Integer, String, VARCHAR, UUID, text
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, declarative_base
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import uuid
from pydantic import BaseModel
from typing import List, Optional


# Create a PostgreSQL engine
engine = create_engine(DATABASE_URL)
Base = declarative_base()


# Define the category table
class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    category_name = Column(String)
    category_id = Column(VARCHAR(255))
    parent_id = Column(VARCHAR(255))
    tenant = Column(String)


# Define the Files table
class Files(Base):
    __tablename__ = 'knowledge_file_info'
    file_name = Column(String)
    file_id = Column(VARCHAR(255), primary_key=True)
    hash_value = Column(String)
    status = Column(String)


# Define the knowledge table
class Knowledge(Base):
    __tablename__ = 'knowledge'
    id = Column(Integer, primary_key=True)
    category_id = Column(VARCHAR(255))
    text = Column(VARCHAR)
    chunk_id = Column(UUID(as_uuid=True))
    file_id = Column(VARCHAR(255))


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


local_embeddings = OllamaEmbeddings(model="bge-m3:latest")
vector_store = PGVector(
    embeddings=local_embeddings,
    collection_name='categoryInfo',
    connection=DATABASE_URL,
    use_jsonb=True
)


conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'my-group',
    'auto.offset.reset': 'earliest',
}


consumer = Consumer(conf)
consumer.subscribe(['panini-ontology-request'])


# Kafka Producer Configuration
producer_conf = {
    'bootstrap.servers': 'localhost:9092'
}
producer = Producer(producer_conf)


# Pydantic models for request and response
class KafkaRequest(BaseModel):
    file_id: Optional[str] = None
    category_id: str = None
    category_name: Optional[str] = None
    learning_obj: Optional[str] = None
    tenant: str = None
    parent_id: Optional[str] = None


class KafkaResponse(BaseModel):
    category_id: Optional[str] = None
    chunk_id: Optional[str] = None
    file_id: Optional[str] = None
    error_message: Optional[str] = None


def send_response(topic: str, response: dict):
    # Create a KafkaResponse object from the response_data dictionary
    response = KafkaResponse(**response)
    # Send the response back to the Kafka topic
    producer.produce(topic, value=response.json())
    producer.flush()
    print("Sent response!")


LOCAL_DIRECTORY = 'knowledge_files'


def custom_deserializer(value):
    if value:
        try:
            return json.loads(value.decode('utf-8'))
        except json.JSONDecodeError:
            return value.decode('utf-8')  # Fallback to plain text
    return None


def process_pdf_file(file_path):
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=0,
        separators=["\n\n", "\n", ".", "\uff0e", "\u3002"]
    )
    all_splits = text_splitter.split_documents(pages)
    return all_splits


def all_categories(category_id):
    session = Session()
    all_category = []
    category_object = session.query(Category).filter_by(parent_id = category_id).all()
    if category_object:
        for category in category_object:
            all_category.append(category.category_id)
            all_category.extend(all_categories(category.category_id))
    return all_category


def main():
    session = Session()
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            try:
                message_value = custom_deserializer(msg.value())
                if message_value is None:
                    print("Received empty message")
                    continue
                print(message_value)
                required_keys = ['file_id', 'category_id', 'category_name', 'tenant', 'parent_id', 'learning_obj']
                # Ensure all necessary fields are present and set missing variables to None
                for key in required_keys:
                    if key not in message_value:
                        message_value[key] = None
                file_id = message_value['file_id']
                category_id = message_value['category_id']
                category_name = message_value['category_name']
                learning_obj = message_value['learning_obj']
                tenant = message_value['tenant']
                parent_id = message_value['parent_id']
                print("Received Items!")
                if category_id:
                    # Check if category_id exists in the database
                    existing_category = session.query(Category).filter_by(category_id=category_id).first()
                    if existing_category:
                        print(f"Category ID {category_id} already exists in the database.")
                        if file_id:
                            # Fetch the file name from the database
                            file_record = session.query(Files).filter(Files.file_id == file_id).first()
                            file_name = file_record.file_name
                            file_path = os.path.join(LOCAL_DIRECTORY, file_name)
                            all_splits = process_pdf_file(file_path)
                            category_ids = all_categories(category_id)
                            if not category_ids:
                                for split in all_splits:
                                    chunk_id = uuid.uuid4()
                                    new_category = Knowledge(category_id=category_id, text=split.page_content, chunk_id=chunk_id, file_id=file_id)
                                    session.add(new_category)
                                    response = {
                                        'category_id': category_id,
                                        'chunk_id': str(chunk_id),
                                        'file_id': file_id,
                                        'error_message': None
                                    }
                                    send_response('panini-ontology-response', response)
                                print("added to knowledge!")
                                session.commit()
                                update_status_query = text("UPDATE knowledge_file_info SET status = 1 WHERE file_id = :file_id")
                                session.execute(update_status_query, {'file_id': file_id})
                                session.commit()
                            else:
                                category_ids = category_ids + [category_id]
                                for split in all_splits:
                                    docs = vector_store.similarity_search(split.page_content, k=1, filter={"id": {"$in": category_ids}})
                                    for doc in docs:
                                        doc_metadata = doc.metadata["id"]
                                        chunk_id = uuid.uuid4()
                                        new_category = Knowledge(category_id=doc_metadata, text=split.page_content, chunk_id=chunk_id, file_id=file_id)
                                        session.add(new_category)
                                        response = {
                                            'category_id': doc_metadata,
                                            'chunk_id': str(chunk_id),
                                            'file_id': file_id,
                                            'error_message': None
                                        }
                                        send_response('panini-ontology-response', response)
                                print("added to knowledge!")
                                session.commit()
                                update_status_query = text("UPDATE knowledge_file_info SET status = 1 WHERE file_id = :file_id")
                                session.execute(update_status_query, {'file_id': file_id})
                                session.commit()
                        else:
                            send_response('panini-ontology-response', {'category_id': None, 'chunk_id': None, 'File_id': None, 'error_message': "Category already exists, provide file id for categorization!"})
                    else:
                        if parent_id:
                            existing_parent_id = session.query(Category).filter_by(category_id=parent_id).first()
                            if existing_parent_id:
                                new_category = Category(category_name=category_name, category_id=category_id, parent_id=parent_id, tenant=tenant)
                                session.add(new_category)
                                print("added to category!")
                                docs = [
                                    Document(
                                        page_content= category_name + learning_obj,
                                        metadata={"id": category_id, "category_name": category_name}
                                    )
                                ]
                                vector_store.add_documents(docs, ids=[doc.metadata["id"] for doc in docs])
                                print("docs added in collection!")
                                send_response('panini-ontology-response', {'category_id': None, 'chunk_id': None, 'File_id': None, 'error_message': "Category created successfully!"})
                            else:
                                send_response('panini-ontology-response', {'category_id': None, 'chunk_id': None, 'File_id': None, 'error_message': "Parent category not found!"})
                        else:
                            new_category = Category(category_name=category_name, category_id=category_id, parent_id=None, tenant=tenant)
                            session.add(new_category)
                            print("added to category!")
                            docs = [
                                Document(
                                    page_content= category_name + learning_obj,
                                    metadata={"id": category_id, "category_name": category_name}
                                )
                            ]
                            vector_store.add_documents(docs, ids=[doc.metadata["id"] for doc in docs])
                            print("docs added in collection!")
                            send_response('panini-ontology-response', {'category_id': None, 'chunk_id': None, 'File_id': None, 'error_message': "Category created successfully!"})
                        if file_id:
                            # Fetch the file name from the database
                            file_record = session.query(Files).filter(Files.file_id == file_id).first()
                            file_name = file_record.file_name
                            file_path = os.path.join(LOCAL_DIRECTORY, file_name)
                            all_splits = process_pdf_file(file_path)
                            for split in all_splits:
                                chunk_id = uuid.uuid4() 
                                new_category = Knowledge(category_id=category_id, text=split.page_content, chunk_id=chunk_id, file_id=file_id)
                                session.add(new_category)
                                response = {
                                    'category_id': doc_metadata,
                                    'chunk_id': str(chunk_id),
                                    'file_id': file_id,
                                    'error_message': None
                                }
                                # list_of_response.append(response)
                                send_response('panini-ontology-response', response)
                            print("added to knowledge!")
                            update_status_query = text("UPDATE knowledge_file_info SET status = 1 WHERE file_id = :file_id")
                            session.execute(update_status_query, {'file_id': file_id})
                    session.commit()
                print("Saved!")
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                continue
    except KeyboardInterrupt:
        print("Shutting down consumer...")
    finally:
        consumer.close()
if __name__ == "__main__":
    main()