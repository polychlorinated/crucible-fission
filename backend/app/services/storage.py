"""Storage service for Google Drive integration."""

import os
from typing import Optional
from sqlalchemy.orm import Session

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import get_settings
from app.models import Asset

settings = get_settings()


def get_drive_service():
    """Get Google Drive service instance."""
    creds = service_account.Credentials.from_service_account_file(
        settings.google_credentials_path,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)


async def upload_to_drive(
    file_path: str,
    filename: str,
    folder_id: Optional[str] = None
) -> str:
    """
    Upload a file to Google Drive.
    
    Returns:
        Google Drive file URL
    """
    service = get_drive_service()
    
    file_metadata = {
        'name': filename,
    }
    
    if folder_id:
        file_metadata['parents'] = [folder_id]
    
    media = MediaFileUpload(file_path, resumable=True)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        supportsAllDrives=True,
        fields='id, name, webViewLink'
    ).execute()
    
    return file.get('webViewLink', '')


async def create_folder(name: str, parent_id: Optional[str] = None) -> str:
    """Create a folder in Google Drive."""
    service = get_drive_service()
    
    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    if parent_id:
        metadata['parents'] = [parent_id]
    
    folder = service.files().create(body=metadata, fields='id').execute()
    return folder['id']


async def upload_project_assets(project_id: str, db: Session):
    """Upload all project assets to Google Drive."""
    from app.models import Project
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    
    # Create folder for this project
    folder_name = f"Fission-{project_id[:8]}"
    folder_id = await create_folder(folder_name)
    
    # Upload each asset
    for asset in project.assets:
        if asset.file_path and os.path.exists(asset.file_path):
            try:
                file_url = await upload_to_drive(
                    asset.file_path,
                    f"{asset.asset_type}_{asset.id[:8]}.mp4",
                    folder_id
                )
                asset.file_url = file_url
                asset.status = "completed"
                db.commit()
            except Exception as e:
                print(f"Error uploading asset {asset.id}: {e}")
                asset.status = "failed"
                db.commit()
    
    return folder_id
