type SearchResultItem = {
  id: string;
  title: string;
  url: string;
  snippet: string;
  siteId: string;
  timestamp: string;
};

type SearchResultsProps = {
  results: SearchResultItem[];
  isLoading: boolean;
  query: string;
};

export function SearchResults({ results, isLoading, query }: SearchResultsProps) {
  if (isLoading) {
    return (
      <div className="w-full max-w-2xl mx-auto mt-6">
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-card border border-border rounded-md p-4">
              <div className="h-4 bg-muted rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-muted rounded w-1/4 mb-2"></div>
              <div className="h-3 bg-muted rounded w-full"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (query && results.length === 0) {
    return (
      <div className="w-full max-w-2xl mx-auto mt-6 text-center p-8 bg-card border border-border rounded-md">
        <h3 className="text-lg font-medium">没有找到匹配的结果</h3>
        <p className="text-muted-foreground mt-2">请尝试其他关键词或减少搜索条件</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto mt-6 space-y-4">
      {results.length > 0 && (
        <p className="text-sm text-muted-foreground">
          找到 {results.length} 条相关结果
        </p>
      )}
      
      {results.map((result) => (
        <div key={result.id} className="bg-card border border-border rounded-md p-4 hover:border-primary/50 transition-colors">
          <h3 className="text-lg font-medium mb-1">
            <a href={result.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              {result.title}
            </a>
          </h3>
          <p className="text-xs text-muted-foreground mb-2">
            {result.url} · {new Date(result.timestamp).toLocaleDateString()}
          </p>
          <p className="text-sm">{result.snippet}</p>
        </div>
      ))}
    </div>
  );
} 