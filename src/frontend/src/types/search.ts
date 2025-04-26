// 搜索结果项类型
export interface SearchResultItem {
  id: string;
  title: string;
  url: string;
  snippet: string;
  content: string;
  score: number;
  created_at: string;
  updated_at: string;
  site_id: string;
  mimetype: string;
  metadata?: Record<string, any>;
}

// 搜索响应类型
export interface SearchResponse {
  query: string;
  results: SearchResultItem[];
  total_count: number;
  page: number;
  top_k: number;
  execution_time_ms: number;
  filters: Record<string, any>;
}

// 搜索参数类型
export interface SearchParams {
  q: string;
  site_id?: string;
  page?: number;
  page_size?: number;
  top_k?: number;
  similarity_cutoff?: number;
  rerank?: boolean;
  rerank_top_k?: number;
  mimetype?: string;
}

// 聊天消息内容类型
export type ChatMessageContent = {
  type: "text";
  text: string;
};

// 聊天消息元数据类型
export type ChatMessageMetadata = {
  timestamp: string;
  deepThink?: boolean;
  references?: Reference[];
};

// 聊天消息接口
export type ChatMessageInterface = {
  content: ChatMessageContent[];
  role: 'user' | 'assistant';
  metadata: ChatMessageMetadata;
};

// API发送消息类型
export type ChatMessageAPI = {
  role: string;
  content: ChatMessageContent[];
};

// 参考资料类型
export type Reference = {
  id: number;
  url: string;
  title: string;
  content: string;
  score?: number;
};

// 聊天响应类型
export type ChatResponse = {
  query: string;
  response: string;
  sources: Reference[];
  execution_time_ms: number;
}; 