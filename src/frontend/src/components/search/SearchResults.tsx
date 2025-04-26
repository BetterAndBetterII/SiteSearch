import React from 'react';
import { SearchResultItem } from '../../types/search';
import { formatDate } from '../../utils/date';

// 高亮处理内容的函数
const highlightContent = (content: string, query: string) => {
  if (!content) return '';
  
  // 如果内容已经包含了高亮标记，直接返回
  if (content.includes('<em>') || content.includes('<strong>')) {
    return content;
  }
  
  // 简单的高亮关键词
  const keywords = query.split(/\s+/).filter(Boolean);
  let highlightedContent = content;
  
  keywords.forEach(keyword => {
    if (keyword.length < 2) return; // 忽略单个字符
    const regex = new RegExp(`(${keyword})`, 'gi');
    highlightedContent = highlightedContent.replace(regex, '<strong>$1</strong>');
  });
  
  return highlightedContent;
};

type SearchResultProps = {
  result: SearchResultItem;
  query: string;
};

// 单个搜索结果组件
const SearchResult: React.FC<SearchResultProps> = ({ result, query }) => {
  // 使用snippet作为摘要，如果没有则使用content的前200个字符
  const displayContent = result.snippet || result.content?.substring(0, 200) + '...';
  const displayTitle = result.title || '无标题';
  
  // 格式化显示的时间
  const formattedDate = formatDate(new Date(result.created_at));
  
  // 处理URL显示
  let displayUrl = result.url;
  try {
    const urlObj = new URL(result.url);
    displayUrl = `${urlObj.hostname}${urlObj.pathname.length > 30 ? urlObj.pathname.substring(0, 30) + '...' : urlObj.pathname}`;
  } catch (e) {
    // 如果URL格式不正确，使用原始URL
  }
  
  return (
    <div className="mb-6 p-4 bg-card rounded-lg border border-border hover:border-primary transition-colors">
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center text-xs text-muted-foreground mb-1">
          <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-full mr-2">
            {result.site_id || '未知站点'}
          </span>
          <span>{formattedDate}</span>
          {result.score > 0 && (
            <span className="ml-2 text-xs text-muted-foreground">
              相关度: {Math.round(result.score * 100)}%
            </span>
          )}
        </div>
      </div>
      
      <h3 className="text-lg font-medium mb-1">
        <a 
          href={result.url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-foreground hover:text-primary hover:underline"
          dangerouslySetInnerHTML={{ __html: highlightContent(displayTitle, query) }}
        />
      </h3>
      
      <div className="text-xs text-muted-foreground mb-2">
        <a 
          href={result.url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="hover:underline"
        >
          {displayUrl}
        </a>
        
        {result.mimetype && (
          <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-secondary text-secondary-foreground">
            {result.mimetype.split('/')[1]?.toUpperCase() || result.mimetype}
          </span>
        )}
      </div>
      
      <div 
        className="text-sm text-muted-foreground whitespace-pre-line line-clamp-4"
        dangerouslySetInnerHTML={{ __html: highlightContent(displayContent, query) }}
      />
    </div>
  );
};

type SearchResultsProps = {
  results: SearchResultItem[];
  isLoading: boolean;
  query: string;
};

export const SearchResults: React.FC<SearchResultsProps> = ({ results, isLoading, query }) => {
  if (isLoading) {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <div className="flex flex-col gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="h-4 bg-muted rounded w-1/4 mb-2"></div>
              <div className="h-6 bg-muted rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-muted rounded w-1/2 mb-3"></div>
              <div className="h-20 bg-muted rounded w-full"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="w-full max-w-2xl mx-auto text-center py-12">
        <p className="text-lg text-muted-foreground">
          没有找到与 "<span className="font-medium text-foreground">{query}</span>" 相关的结果
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          请尝试其他关键词或减少筛选条件
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="flex flex-col gap-2">
        {results.map((result) => (
          <SearchResult key={result.id} result={result} query={query} />
        ))}
      </div>
    </div>
  );
}; 