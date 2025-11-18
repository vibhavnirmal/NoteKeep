# Image Upload Feature for Personal Notes

## Overview
Added image upload capability to personal notes with automatic compression to keep images under 100KB while maintaining quality.

## Changes Made

### 1. Database Schema
- **File**: `app/models.py`
- Added `image_url` field to `Note` model (VARCHAR 500, nullable)
- Stores base64-encoded image data directly in database

### 2. Pydantic Schemas
- **File**: `app/schemas.py`
- Updated `NoteBase` schema with `image_url` field
- Updated `NoteUpdate` schema to accept image updates

### 3. Image Processing Utility
- **File**: `app/image_utils.py` (NEW)
- **Function**: `compress_image(image_data: bytes, max_size_kb: int = 100) -> str`
  - Converts RGBA/LA/P images to RGB
  - Iteratively reduces quality (95 → 20) until under size limit
  - Resizes image if quality reduction isn't enough
  - Returns base64-encoded data URL (e.g., "data:image/jpeg;base64,...")
- **Function**: `validate_image(image_data: bytes) -> bool`
  - Validates uploaded data is a valid image

### 4. Web Routes
- **File**: `app/routers/web.py`
- **Updated**: `/notes/create` route
  - Now accepts `image: UploadFile | None = File(None)`
  - Validates and compresses image before saving
  - Handles upload errors gracefully
- **Updated**: `/notes/{note_id}/update` route
  - Accepts new image uploads
  - Supports `remove_image` checkbox to delete current image
  - Preserves existing image if no changes

### 5. Templates

#### add.html (Note Creation)
- Changed form encoding to `enctype="multipart/form-data"`
- Added file input with accept="image/*"
- Added image preview functionality with JavaScript
- Shows "Remove image" button when image selected
- Displays compression info message

#### note_detail.html (Note Edit)
- Changed form encoding to `enctype="multipart/form-data"`
- Displays current image if exists
- Added "Remove current image" checkbox
- Added new image upload input
- Image preview for new uploads
- JavaScript preview functionality

#### links.html (Note Cards)
- Updated note card to display image thumbnail if exists
- Falls back to purple file-text icon if no image
- Image fills the 64x64px thumbnail space with object-cover

### 6. Dependencies
- **File**: `requirements.txt`
- Added `Pillow>=10.0.0` for image processing

## How It Works

### Upload Flow
1. User selects image file in form
2. JavaScript shows preview before upload
3. Form submits with multipart/form-data
4. Backend receives UploadFile
5. Image validation with PIL
6. Compression to <100KB:
   - Start with quality=95
   - Reduce by 5 until under limit
   - Resize if needed
7. Base64 encode and create data URL
8. Store in database as string

### Display Flow
1. Note retrieved from database with image_url
2. Template checks `{% if note.image_url %}`
3. Renders `<img src="{{ note.image_url }}">`
4. Browser decodes base64 data URL automatically

### Storage Strategy
- **Method**: Base64 data URLs stored directly in database
- **Pros**: 
  - No filesystem management
  - No static file serving configuration
  - Easy backup (everything in DB)
  - Works with SQLite
- **Cons**: 
  - Larger database size
  - Slower queries if many images
- **Alternative**: Could switch to file storage in `/static/uploads/notes/` if needed

## Testing

### Create Note with Image
1. Go to `/add#note`
2. Fill title and content
3. Select image file
4. See preview
5. Submit
6. Check `/links` - note card shows thumbnail

### Update Note Image
1. Open existing note
2. Upload new image or check "Remove current image"
3. Save changes
4. Verify image updated/removed

### Compression Test
1. Upload large image (>1MB)
2. Check network tab - response includes compressed base64
3. Verify visual quality acceptable

## Future Enhancements
- [ ] Support multiple images per note
- [ ] Switch to filesystem storage for better performance
- [ ] Add image editor (crop, rotate, filters)
- [ ] Support drag & drop upload
- [ ] Paste from clipboard
- [ ] WebP format for better compression
- [ ] Lazy loading for images in list view
