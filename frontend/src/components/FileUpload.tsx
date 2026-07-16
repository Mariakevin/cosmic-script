import { useCallback, useRef, useState } from 'react';
import { uploadDocument } from '../api/client';
import type { UploadResponse } from '../types';

interface FileUploadProps {
  onUploadComplete: (data: UploadResponse) => void;
  onError: (msg: string) => void;
}

type InputMode = 'upload' | 'text';

export function FileUpload({ onUploadComplete, onError }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<InputMode>('upload');
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [textInput, setTextInput] = useState('');

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

  const handleTextSubmit = useCallback(() => {
    const text = textInput.trim();
    if (!text) {
      onError('Please enter some text');
      return;
    }
    if (text.split(/\s+/).length < 50) {
      onError('Please enter at least 50 words for a meaningful conversion');
      return;
    }
    // Construct UploadResponse from typed text (no file needed)
    const words = text.split(/\s+/);
    const response: UploadResponse = {
      filename: 'pasted-text.txt',
      text,
      word_count: words.length,
      char_count: text.length,
      char_count_no_spaces: text.replace(/\s/g, '').length,
    };
    onUploadComplete(response);
  }, [textInput, onUploadComplete, onError]);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    // Allow normal paste behavior in textarea
  }, []);

  return (
    <div className="card">
      {/* Mode Tabs */}
      <div className="input-tabs">
        <button
          className={`input-tab ${mode === 'upload' ? 'active' : ''}`}
          onClick={() => setMode('upload')}
          type="button"
        >
          <span className="input-tab-icon">{'\uD83D\uDCC1'}</span>
          Upload File
        </button>
        <button
          className={`input-tab ${mode === 'text' ? 'active' : ''}`}
          onClick={() => setMode('text')}
          type="button"
        >
          <span className="input-tab-icon">{'\u270D\uFE0F'}</span>
          Type / Paste Text
        </button>
      </div>

      {/* Upload Mode */}
      {mode === 'upload' && (
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
      )}

      {/* Text Mode */}
      {mode === 'text' && (
        <div className="text-input-area">
          <textarea
            className="text-input"
            placeholder="Paste or type your story here...&#10;&#10;The chapterizer will automatically detect chapters, and the AI will convert each chapter into screenplay format.&#10;&#10;Tip: Longer texts (1000+ words) work best for conversion."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onPaste={handlePaste}
            rows={14}
            aria-label="Story text input"
          />
          <div className="text-input-footer">
            <span className="text-input-count">
              {textInput ? `${textInput.split(/\s+/).filter(Boolean).length} words` : 'Start typing...'}
            </span>
            <button
              className="btn btn-primary"
              onClick={handleTextSubmit}
              disabled={!textInput.trim()}
            >
              Use This Text
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
