// 搜索结果项类型
export type SearchResultItem = {
  id: number;
  url: string;
  title: string;
  description: string;
  content: string;
  mimetype: string;
  content_hash: string;
  created_at: string;
  updated_at: string;
  timestamp: number;
  score: number;
  site_ids: string[];
  highlights?: {
    title?: string;
    description?: string;
    content?: string;
  };
};

// 搜索响应类型
export type SearchResponse = {
  query: string;
  results: SearchResultItem[];
  total_count: number;
  page: number;
  page_size: number;
  execution_time_ms: number;
  filters?: {
    site_id?: string;
  };
}; 