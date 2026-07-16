import axios from 'axios';
import type {
  UploadResponse,
  ChaptersResponse,
  ConvertRequest,
  ScreenplayResponse,
  ExportRequest,
  ExportResponse,
  ValidationResponse,
  CharactersResponse,
  ModelsResponse,
  GenresResponse,
  CoverageResponse,
  LoglineResponse,
  PageEstimateResponse,
} from '../types';

const api = axios.create({
  baseURL: '',
  timeout: 300000,
});

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<UploadResponse>('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function extractChapters(text: string): Promise<ChaptersResponse> {
  const { data } = await api.post<ChaptersResponse>('/api/chapters', { text });
  return data;
}

export async function convertToScreenplay(request: ConvertRequest): Promise<ScreenplayResponse> {
  const { data } = await api.post<ScreenplayResponse>('/api/convert', request);
  return data;
}

export async function exportScreenplay(request: ExportRequest): Promise<ExportResponse> {
  const { data } = await api.post<ExportResponse>('/api/export', request);
  return data;
}

export async function validateFountain(text: string): Promise<ValidationResponse> {
  const { data } = await api.post<ValidationResponse>('/api/validate', { text });
  return data;
}

export async function extractCharacters(text: string): Promise<CharactersResponse> {
  const { data } = await api.post<CharactersResponse>('/api/characters', { text });
  return data;
}

export async function getModels(): Promise<ModelsResponse> {
  const { data } = await api.get<ModelsResponse>('/api/convert/models');
  return data;
}

export async function getHealth(): Promise<{ status: string }> {
  const { data } = await api.get<{ status: string }>('/health');
  return data;
}

export async function getGenres(): Promise<GenresResponse> {
  const { data } = await api.get<GenresResponse>('/api/genres');
  return data;
}

export async function generateCoverage(text: string, model?: string): Promise<CoverageResponse> {
  const { data } = await api.post<CoverageResponse>('/api/coverage', { text }, {
    params: model ? { model } : undefined,
  });
  return data;
}

export async function generateLogline(text: string, model?: string): Promise<LoglineResponse> {
  const { data } = await api.post<LoglineResponse>('/api/logline', { text }, {
    params: model ? { model } : undefined,
  });
  return data;
}

export async function estimatePages(text: string): Promise<PageEstimateResponse> {
  const { data } = await api.get<PageEstimateResponse>('/api/estimate', {
    params: { text },
  });
  return data;
}
