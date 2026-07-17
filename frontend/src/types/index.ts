export interface UploadResponse {
  filename: string;
  text: string;
  word_count: number;
  char_count: number;
  char_count_no_spaces: number;
}

export interface ChapterResponse {
  number: number;
  title: string | null;
  text_preview: string;
}

export interface ChaptersResponse {
  chapters: ChapterResponse[];
}

export interface ConvertRequest {
  text: string;
  title?: string;
  author?: string;
  genre?: string;
}

export interface GenreInfo {
  name: string;
  description: string;
}

export interface GenresResponse {
  genres: GenreInfo[];
}

export interface CoverageResponse {
  logline: string;
  synopsis: string;
  strengths: string[];
  weaknesses: string[];
  rating: number;
  recommendation: string;
  genre: string;
  target_audience: string;
  model_used: string;
}

export interface LoglineResponse {
  logline: string;
}

export interface PageEstimateResponse {
  estimated_pages: number;
  total_lines: number;
  breakdown: Record<string, number>;
  confidence: string;
}

export interface SceneResponse {
  heading: string;
  content: string;
}

export interface ElementResponse {
  type: string;
  text: string;
}

export interface ScreenplayResponse {
  title: string | null;
  author: string | null;
  scenes: SceneResponse[];
  elements: ElementResponse[];
}

export interface ExportRequest {
  screenplay: ScreenplayResponse;
  format: string;
}

export interface ExportResponse {
  content: string;
  format: string;
}

export interface ValidationItem {
  line: number | null;
  message: string;
  severity: string;
  code: string | null;
}

export interface ValidationResponse {
  errors: ValidationItem[];
  warnings: ValidationItem[];
  infos: ValidationItem[];
}

export interface CharacterResponse {
  canonical_name: string;
  aliases: string[];
  first_appearance: string | null;
}

export interface CharactersResponse {
  characters: CharacterResponse[];
}

export interface ErrorResponse {
  error: string;
  detail?: string;
  line?: number;
}

// ── Voice Analysis ──────────────────────────────────────────────────────

export interface VoiceCharacter {
  name: string;
  line_count: number;
  vocabulary_richness: number;
  speaking_style: string;
  emotional_tone: string;
}

export interface VoiceResponse {
  characters: VoiceCharacter[];
  overall_style: string;
}

// ── Pacing Analysis ─────────────────────────────────────────────────────

export interface PacingScene {
  heading: string;
  dialogue_ratio: number;
  pacing: 'fast' | 'medium' | 'slow';
  word_count: number;
  issues: string[];
  recommendations: string[];
}

export interface PacingResponse {
  scenes: PacingScene[];
  average_dialogue_ratio: number;
  overall_pacing: string;
  recommendations: string[];
}
