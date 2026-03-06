export type NewsSourceType = "news" | "x" | "blog" | "research" | "other";

export interface AiNewsItem {
  id: string;
  title: string;
  url: string;
  summary: string;
  source: string;
  source_type: NewsSourceType | string;
  published_at: string | null;
  relevance_score: number;
  tags: string[];
}

export interface AiNewsResponse {
  success: boolean;
  generated_at: string;
  query: string;
  scanned_sources: number;
  failed_sources: number;
  source_errors: string[];
  items: AiNewsItem[];
}
