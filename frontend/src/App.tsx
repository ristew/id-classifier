import React, { useState, useEffect, ChangeEvent, FormEvent } from 'react';
import './App.css';

// --- Interfaces ---
interface ExtractedFeatures {
  [key: string]: string | null;
}

// Matches schemas.DocumentRecordResponse from backend
interface DocumentRecord {
  id: number;
  original_filename: string;
  image_base64: string; // This is the data URL (e.g., "data:image/png;base64,...")
  document_type: string;
  features: ExtractedFeatures;
  created_at: string; // ISO date string
  updated_at: string; // ISO date string
}

const API_BASE_URL = "http://localhost:8000";
const NOT_FOUND_PLACEHOLDER_DISPLAY = "N/A";
const HISTORY_LIMIT = 5;

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localImagePreviewUrl, setLocalImagePreviewUrl] = useState<string | null>(null); // For preview of unsaved file

  const [currentDocument, setCurrentDocument] = useState<DocumentRecord | null>(null);
  const [editedFeatures, setEditedFeatures] = useState<ExtractedFeatures | null>(null);
  // No need for separate currentDocumentId, it's in currentDocument.id

  const [isLoading, setIsLoading] = useState<boolean>(false); // For /classify
  const [isSaving, setIsSaving] = useState<boolean>(false); // For PUT /documents/{id}
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  const [history, setHistory] = useState<DocumentRecord[]>([]);

  // Fetch initial history
  useEffect(() => {
    fetchHistory();
  }, []);

  // When currentDocument changes (e.g. loaded from history or after /classify)
  useEffect(() => {
    if (currentDocument) {
      setEditedFeatures({ ...currentDocument.features });
      // Image for currentDocument is its image_base64, not local preview
      setLocalImagePreviewUrl(null); // Clear local preview if a document is loaded
    } else {
      // If currentDocument is cleared, clear edited features
      setEditedFeatures(null);
    }
  }, [currentDocument]);

  // Cleanup local object URL
  useEffect(() => {
    return () => {
      if (localImagePreviewUrl) {
        URL.revokeObjectURL(localImagePreviewUrl);
      }
    };
  }, [localImagePreviewUrl]);

  const clearMessages = () => {
    setError(null);
    setSuccessMessage(null);
  };

  const resetToUploadState = () => {
    setSelectedFile(null);
    setLocalImagePreviewUrl(null);
    setCurrentDocument(null); // This will clear editedFeatures via useEffect
    clearMessages();
    // Optionally clear the file input visually if needed
    const fileInput = document.getElementById('file-upload-input') as HTMLInputElement;
    if (fileInput) fileInput.value = "";
  }

  const fetchHistory = async () => {
    try {
      setIsLoading(true); // General loading indicator for history fetch too
      const response = await fetch(`${API_BASE_URL}/documents/?limit=${HISTORY_LIMIT}`);
      if (!response.ok) {
        const errData = await response.json().catch(() => ({detail: "Failed to fetch history"}));
        throw new Error(errData.detail || 'Failed to fetch history');
      }
      const data: DocumentRecord[] = await response.json();
      setHistory(data);
    } catch (err: any) {
      setError(`History Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    // When a new file is selected, we are in "new upload" mode.
    // Clear any currently loaded document.
    setCurrentDocument(null);
    setEditedFeatures(null);
    clearMessages();

    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      const previewUrl = URL.createObjectURL(file);
      setLocalImagePreviewUrl(previewUrl);
    } else {
      setSelectedFile(null);
      setLocalImagePreviewUrl(null);
    }
  };

  const handleExtractAndSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setError("Please select an image file first.");
      return;
    }

    setIsLoading(true);
    clearMessages();
    // We are creating a new document, so clear any existing currentDocument
    setCurrentDocument(null); 

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/classify`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({detail: `API Error: ${response.statusText}`}));
        throw new Error(errorData.detail || `API Error: ${response.statusText}`);
      }

      const newDocument: DocumentRecord = await response.json();
      setCurrentDocument(newDocument); // This will set editedFeatures via useEffect
      setSuccessMessage(`Document "${newDocument.original_filename}" processed and saved! ID: ${newDocument.id}`);
      fetchHistory(); // Refresh history
      // After successful save, clear selected file state but keep currentDocument displayed
      setSelectedFile(null); 
      // localImagePreviewUrl is already null because currentDocument is set

    } catch (err: any) {
      setError(`Extraction Error: ${err.message}`);
      console.error("Extraction error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeatureChange = (featureKey: string, value: string) => {
    setEditedFeatures(prev => {
      if (!prev) return null;
      const actualValue = value === NOT_FOUND_PLACEHOLDER_DISPLAY ? null : value;
      return { ...prev, [featureKey]: actualValue };
    });
    setSuccessMessage(null); // Clear any success message on edit
  };

  const handleSaveChanges = async () => {
    if (!currentDocument || !editedFeatures) {
      setError("No document loaded or no features to save.");
      return;
    }

    setIsSaving(true);
    clearMessages();

    const updatePayload: { features: ExtractedFeatures; document_type?: string } = {
      features: editedFeatures,
    };
    // Optionally, if you allow editing document_type in the UI and it's part of editedFeatures:
    // if (editedFeatures.document_type && editedFeatures.document_type !== currentDocument.document_type) {
    //   updatePayload.document_type = editedFeatures.document_type;
    // }

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${currentDocument.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatePayload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({detail: `API Error: ${response.statusText}`}));
        throw new Error(errorData.detail || `API Error: ${response.statusText}`);
      }

      const updatedDocument: DocumentRecord = await response.json();
      setCurrentDocument(updatedDocument); // Update current document with saved data
      setSuccessMessage(`Changes for "${updatedDocument.original_filename}" saved successfully!`);
      fetchHistory(); // Refresh history as an item might have been updated
    } catch (err: any) {
      setError(`Save Error: ${err.message}`);
      console.error("Save error:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadFromHistory = (item: DocumentRecord) => {
    clearMessages();
    setCurrentDocument(item); // This will trigger useEffect for editedFeatures and image
    setSelectedFile(null);    // Clear any locally selected file
    setLocalImagePreviewUrl(null); // Ensure local preview is cleared
    window.scrollTo(0, 0);
  };

  const hasUnsavedChanges = () => {
    if (!currentDocument || !editedFeatures) return false;
    return JSON.stringify(currentDocument.features) !== JSON.stringify(editedFeatures);
  };

  // Determine which image URL to show: local preview or from currentDocument
  const displayImageUrl = localImagePreviewUrl || (currentDocument ? currentDocument.image_base64 : null);

  return (
    <div className="App">
      <main>
        <section className="upload-section">
          <h2>Upload Image</h2>
          <form onSubmit={handleExtractAndSave}>
            <input id="file-upload-input" type="file" accept="image/jpeg, image/png, image/webp" onChange={handleFileChange} />
            <button type="submit" disabled={!selectedFile || isLoading}>
              {isLoading ? 'Processing...' : 'Extract & Save New'}
            </button>
          </form>
          {currentDocument && (
            <button onClick={resetToUploadState} className="clear-button">
              Clear Current / Upload New
            </button>
          )}
          {error && <p className="error-message">{error}</p>}
          {successMessage && <p className="success-message">{successMessage}</p>}
        </section>

        <div className="content-area">
          <section className="image-preview-section">
            <h2>Preview</h2>
            {displayImageUrl ? (
              <img src={displayImageUrl} alt="Document" className="preview-image" />
            ) : (
              <p>No image selected or loaded.</p>
            )}
            {currentDocument && <p className="filename-display">Viewing: {currentDocument.original_filename} (ID: {currentDocument.id})</p>}
            {selectedFile && !currentDocument && <p className="filename-display">New Upload: {selectedFile.name}</p>}
          </section>

          {currentDocument && editedFeatures && (
            <section className="extraction-results-section">
              <h2>Extracted Fields</h2>
              <p><strong>Document Type:</strong> {currentDocument.document_type.replace(/_/g, ' ').toUpperCase()}</p>
              {/* Consider allowing document_type editing if needed */}
              <div className="features-grid">
                {Object.entries(editedFeatures).map(([key, value]) => (
                  <div key={key} className="feature-item">
                    <label htmlFor={`feature-${key}`}>{key.replace(/_/g, ' ')}:</label>
                    <input
                      type="text"
                      id={`feature-${key}`}
                      value={value === null ? NOT_FOUND_PLACEHOLDER_DISPLAY : value as string}
                      onChange={(e) => handleFeatureChange(key, e.target.value)}
                      className={value === null ? 'not-found' : ''}
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={handleSaveChanges}
                disabled={isSaving || !hasUnsavedChanges()}
                className="save-changes-button"
              >
                {isSaving ? 'Saving...' : 'Save Changes to This Document'}
              </button>
            </section>
          )}
        </div>

        {history.length > 0 && (
          <section className="history-section">
            <h2>Last {HISTORY_LIMIT} Documents</h2>
            <div className="history-grid">
              {history.map((item) => (
                <div key={item.id} className={`history-item ${currentDocument?.id === item.id ? 'active' : ''}`} onClick={() => handleLoadFromHistory(item)}>
                  <img src={item.image_base64} alt={item.original_filename} />
                  <p><strong>ID: {item.id}</strong></p>
                  <p><strong>Type:</strong> {item.document_type.replace(/_/g, ' ')}</p>
                  <p title={item.original_filename}>
                    <strong>File:</strong> {item.original_filename.length > 15 ? item.original_filename.substring(0,12) + "..." : item.original_filename}
                  </p>
                  <small>Updated: {new Date(item.updated_at).toLocaleDateString()}</small>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
      <footer>
        <p>ID Document Classifier Frontend v1.2.0</p>
      </footer>
    </div>
  );
}

export default App;
