import { useCallback, useRef, useState } from 'react';
import { uploadDocument } from '../api/client';
import type { UploadResponse } from '../types';

interface FileUploadProps {
  onUploadComplete: (data: UploadResponse) => void;
  onError: (msg: string) => void;
}

export function FileUpload({ onUploadComplete, onError }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.match(/\.(txt|docx?|epub|pdf|md|fountain)$/i)) {
      onError('Unsupported file type. Use .txt, .docx, .epub, .pdf, .md, or .fountain');
      return;
    }
    setUploading(true);
    try {
      const data = await uploadDocument(file);
      onUploadComplete(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      onError(msg);
    } finally {
      setUploading(false);
    }
  }, [onUploadComplete, onError]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <div className="card">
      <div
        className={`file-upload ${dragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
        aria-label="Upload a story file"
      >
        <div className="file-upload-icon">
          {uploading ? '\u23F3' : '\uD83C\uDFAC'}
        </div>
        <p>{uploading ? 'Uploading...' : 'Drop a story file here'}</p>
        <p className="file-upload-hint">
          Supports .txt, .docx, .epub, .pdf, .md, .fountain
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".txt,.docx,.epub,.pdf,.md,.fountain"
          onChange={handleChange}
          hidden
        />
        <button
          className="btn btn-primary"
          onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
          disabled={uploading}
          style={{ marginTop: 16 }}
        >
          {uploading ? 'Uploading...' : 'Select File'}
        </button>
      </div>
    </div>
  );
}
