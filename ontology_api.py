from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from sqlalchemy import create_engine, Column, String, Integer, VARCHAR, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict
from uuid import UUID as PyUUID
from pydantic import BaseModel
import os# print(cleaned_chunks)
import hashlib
from env import DATABASE_URL
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html
)   


app = FastAPI()


# Create a PostgreSQL engine
engine = create_engine(DATABASE_URL)
Base = declarative_base()


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


# Define the category table
class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    category_name = Column(String)
    category_id = Column(VARCHAR(255))
    parent_id = Column(VARCHAR(255))
    tenant = Column(String)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


# Define Pydantic models for requests
class UploadFilesApiResponse(BaseModel):
    success: bool
    message: Optional[str]
    file_name: Optional[str]


class ChunkRequest(BaseModel):
    chunk_ids: List[str]


class ChunkData(BaseModel):
    chunk_id: str
    file_id: str  # Adjust the type if `file_id` is an integer
    text: str


class ChunksResponse(BaseModel):
    success: bool
    message: Optional[str]
    chunk_details: Optional[List[ChunkData]]
    not_found_chunk_ids: Optional[List[str]]


class UpdateCategoryRequest(BaseModel):
    chunk_id: str
    category_id: str


class UpdateCategoryResponse(BaseModel):
    success: bool
    message: Optional[str]
    chunk_id: Optional[str]
    category_id: Optional[str]


# Pydantic model for the request body
class DeleteCategoryRequest(BaseModel):
    category_id: str
UPLOAD_DIRECTORY = "knowledge_files"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)



def all_categories(category_id):
    session = Session()
    all_category = []
    category_object = session.query(Category).filter(Category.parent_id == category_id).all()
    if category_object is not None:
        for category in category_object:
            all_category.append(category.category_id)
            all_category.extend(all_categories(category.category_id))
    return all_category



@app.post("/files", tags=["files"])
async def upload_file(file: UploadFile = File(...),file_id: str = Body(...),hash_value: str = Body(...)) -> UploadFilesApiResponse:
    """
    Upload files to the server, validate their content, and store metadata in the database.
    
    This endpoint accepts one or more files, checks their extension and hash value,
    and stores them in a local directory. If a file with the same hash value already 
    exists, it prevents duplication. Additionally, it ensures that each file's name 
    is unique in the database. If a file name conflict is detected, it appends a 
    counter to the filename to resolve the conflict.
    
    Args:
        files: A list of file uploads (only .pdf files allowed).
        file_id: A unique identifier for the file.
        hash_value: The SHA-256 hash of the file content for validation.
    Returns:
        UploadFilesApiResponse: A response containing a 
        success : status of the response, 
        message : indicate the outcome of the upload file and error messages 
        final_name : uploaded file name or existing file name if any.
    """
    session = Session()
    response = []
    allowed_extensions = {".pdf"}
    original_file_name = file.filename
    file_extension = os.path.splitext(original_file_name)[1].lower()
    try:
        # Check if the file extension is allowed
        if file_extension not in allowed_extensions:
            return UploadFilesApiResponse(success=False, message="Provided file type is not valid.", file_name=original_file_name)
        
        # Read file content into memory
        file_content = await file.read()
        generated_hash_value = hashlib.sha256(file_content).hexdigest()
        
        # Check if the provided hash_value matches the calculated hash_value
        if hash_value != generated_hash_value:
            return UploadFilesApiResponse(success=False, message="Provided hash value does not match the calculated hash value.", file_name=original_file_name)
        
        existing_file = session.query(Files).filter(Files.hash_value == hash_value).first()
        
        if existing_file:
            return UploadFilesApiResponse(success=False, message="File already exists.", file_name=existing_file.file_name)
        # Check if the file name already exists in the database
        existing_file = session.query(Files).filter(Files.file_name == original_file_name).first()
        new_file_name = original_file_name
        
        # If the file name exists, rename it
        counter = 1
        while existing_file:
            new_file_name = f"{os.path.splitext(original_file_name)[0]}({counter}){file_extension}"
            existing_file = session.query(Files).filter(Files.file_name == new_file_name).first()
            counter += 1
        
        # Create a new file record
        new_file = Files(file_name=new_file_name, file_id=file_id, hash_value=hash_value, status="0")
        session.add(new_file)
        # Save the file to the local directory
        file_location = os.path.join(UPLOAD_DIRECTORY, new_file_name)
        with open(file_location, "wb") as f:
            f.write(file_content)  # Write the content read into memory
            
        session.commit()
        return UploadFilesApiResponse(success=True, message="File uploaded successfully", file_name=new_file_name)
    except Exception as e:
        session.rollback()
        return UploadFilesApiResponse(success=False, message=f"error: {str(e)}", file_name=None)
    


@app.post("/chunks", tags=["chunks"])
async def get_chunks(chunk_request: ChunkRequest) -> ChunksResponse:
    """
    Retrieve text chunks from the database based on the provided chunk IDs.
    This endpoint accepts a list of chunk IDs and retrieves the corresponding 
    text chunks from the database. It also validates if the requested chunk IDs exist.
    If no chunk IDs are provided, or if some IDs do not correspond to any chunks 
    in the database, it returns an informative message with the operation's result.
    Args:
        chunk_request (ChunkRequest): An object containing a list of chunk IDs to retrieve from the database.
    Returns:
        ChunksResponse: An object containing:
            - success (bool): Indicates whether the operation was successful.
            - message (str): A message providing additional context about the response (e.g., success, details of missing IDs).
            - chunk_details (List[ChunkData] or None): A list of ChunkData objects containing details of the retrieved chunks, where each 
              ChunkData object includes:
                - chunk_id (str): The ID of the chunk.
                - file_id (str): The ID of the file associated with the chunk.
                - text (str): The text content of the chunk.
            - not_found_chunk_ids (List[str] or None): A list of chunk IDs that were requested but not found in the database. This field is included when some provided chunk IDs do not match any entries in the database.
    """
    chunk_ids = chunk_request.chunk_ids
    if not chunk_ids:
        return ChunksResponse(success=False, message="Chunk IDs must be provided.", chunk_details=None, not_found_chunk_ids=None)
    session = Session()
    try:
        # Convert string UUIDs to UUID instances
        uuid_chunk_ids_for_validations = set(PyUUID(chunk_id) for chunk_id in chunk_ids)
        uuid_chunk_ids = [PyUUID(chunk_id) for chunk_id in chunk_ids]
        chunks = session.query(Knowledge).filter(Knowledge.chunk_id.in_(uuid_chunk_ids)).all()
        # Prepare the result as a dictionary with chunk IDs as keys and text as values
        result = [ChunkData(chunk_id=str(chunk.chunk_id), file_id=chunk.file_id, text=chunk.text)for chunk in chunks]
        # Create a set of chunk IDs retrieved from the database
        retrieved_chunk_ids = set(chunk.chunk_id for chunk in chunks)
        # Check for missing chunk IDs
        missing_chunk_ids = uuid_chunk_ids_for_validations - retrieved_chunk_ids
        if missing_chunk_ids:
            missing_ids_message = [str(chunk_id) for chunk_id in missing_chunk_ids]
            return ChunksResponse(success=False, message="successfully retrieved some chunk details, but some IDs were not found in the database.", chunk_details=result, not_found_chunk_ids=missing_ids_message)
        # Return the result
        if not result:
            return ChunksResponse(success=True, message="No chunks found for the provided chunk IDs.", chunk_details=None, not_found_chunk_ids=None)
        return ChunksResponse(success=True, message="Successfully retrieved chunk details.", chunk_details=result, not_found_chunk_ids=None)
    except Exception as e:
        return ChunksResponse(success=False, message=f"error: {str(e)}", chunk_details=None, not_found_chunk_ids=None)
    finally:
        session.close()



@app.put("/updateCategory", tags=["updateCategory"])
async def update_category(update_request: UpdateCategoryRequest) -> UpdateCategoryResponse:
    """
    Update the category ID for a specific chunk ID if it is not already associated.
    Args:
    update_request: Object containing chunk ID and the new category ID to set if necessary.
    Returns:
    dict: A message indicating the status of the update.
    """
    session = Session()
    try:
        # Convert string UUID to UUID instance
        chunk_id = update_request.chunk_id
        category_id = update_request.category_id
        # Query to find the Knowledge entry with the given chunk_id
        knowledge_entry = session.query(Knowledge).filter(Knowledge.chunk_id == chunk_id).first()
        # If the Knowledge entry doesn't exist, raise an error
        if knowledge_entry is None:
            return UpdateCategoryResponse(success=True, message="Chunk ID not found in the database.", chunk_id=chunk_id, category_id=category_id)
        # Check if the current category ID is the same as the requested one
        if knowledge_entry.category_id == update_request.category_id:
            return UpdateCategoryResponse(success=True, message="Category ID is already up to date.", chunk_id=chunk_id, category_id=category_id)
        # If not, update the category ID
        knowledge_entry.category_id = update_request.category_id
        session.commit()
        return UpdateCategoryResponse(success=True, message="Category ID updated successfully.", chunk_id=chunk_id, category_id=category_id)
    except Exception as e:
        session.rollback()  # Rollback in case of an error
        return UpdateCategoryResponse(success=False, message=f"error: {str(e)}", chunk_id=None, category_id=None)
    finally:
        session.close()


        
@app.delete("/deleteCategory", tags=["deleteCategories"])
async def delete_categories(request: DeleteCategoryRequest):
    """
    Delete the category ID for a specific category_id.
    Args:
    delete_request: it will take the category_id to delete operation.
    Returns:
    dict: A message indicating the status of the delete.
    """
    category_id = request.category_id  # Get category_id from the request body
    session = Session()
    try:
        category_ids = all_categories(category_id)
        category_ids.append(category_id)
        categories_to_delete = session.query(Category).filter(Category.category_id.in_(category_ids)).all()
        if not categories_to_delete:
            raise HTTPException(status_code=404, detail="No categories found with the given parent ID")
        for category in categories_to_delete:
            session.delete(category)
        session.commit() 
        return JSONResponse(status_code=200, content={"message": "Category deleted successfully"})
    except Exception as e:
        session.rollback() 
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()