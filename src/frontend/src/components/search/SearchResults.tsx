import React from 'react';
import { SearchResultItem } from '../../types/search';
import { formatDate } from '../../utils/date';

// 高亮处理内容的函数
const highlightContent = (content: string) => {
  // 处理加粗的内容（**内容**）
  return content.replace(/\*\*([^*]+)\*\*/g, '<span class="font-bold text-primary">$1</span>');
};

type SearchResultProps = {
  result: SearchResultItem;
};

// 单个搜索结果组件
const SearchResult: React.FC<SearchResultProps> = ({ result }) => {
  const displayContent = result.highlights?.content || result.content;
  const displayTitle = result.highlights?.title || result.title;
  
  // 格式化显示的时间
  const formattedDate = formatDate(result.timestamp * 1000);
  
  // 处理URL显示
  const urlObj = new URL(result.url);
  const displayUrl = `${urlObj.hostname}${urlObj.pathname.length > 30 ? urlObj.pathname.substring(0, 30) + '...' : urlObj.pathname}`;
  
  // 提取站点ID显示
  const siteId = result.site_ids[0] || '';
  
  return (
    <div className="mb-6 p-4 bg-card rounded-lg border border-border hover:border-primary transition-colors">
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center text-xs text-muted-foreground mb-1">
          <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-full mr-2">
            {siteId.replace('_demo', '').replace('-demo', '')}
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
          dangerouslySetInnerHTML={{ __html: highlightContent(displayTitle) }}
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
      </div>
      
      <div 
        className="text-sm text-muted-foreground whitespace-pre-line line-clamp-4"
        dangerouslySetInnerHTML={{ __html: highlightContent(displayContent) }}
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
          <SearchResult key={result.id} result={result} />
        ))}
      </div>
    </div>
  );
}; 