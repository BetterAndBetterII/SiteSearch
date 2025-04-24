import { useState, useEffect } from 'react';
import { SearchBar } from '../components/search/SearchBar';
import { SearchResults } from '../components/search/SearchResults';
import { searchApi, siteApi } from '../api/index';
import { SearchResultItem, SearchResponse } from '../types/search';

// 站点类型
type Site = {
  id: string;
  name: string;
  url: string;
};

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [totalResults, setTotalResults] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [error, setError] = useState<string | null>(null);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [isLoadingSites, setIsLoadingSites] = useState(false);

  // 获取可用站点列表
  useEffect(() => {
    const fetchSites = async () => {
      setIsLoadingSites(true);
      try {
        const sitesData = await siteApi.getSites();
        setSites(sitesData.results);
      } catch (error) {
        console.error('获取站点列表失败:', error);
      } finally {
        setIsLoadingSites(false);
      }
    };

    fetchSites();
  }, []);

  // 执行搜索
  const fetchSearchResults = async (searchQuery: string, currentPage = 1) => {
    if (!searchQuery.trim()) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // 构造搜索参数
      const searchParams: any = {
        q: searchQuery,
        page: currentPage,
        page_size: pageSize
      };
      
      // 如果选择了特定站点，添加站点ID参数
      if (selectedSiteId) {
        searchParams.site_id = selectedSiteId;
      }
      
      // 调用语义搜索API
      const response = await searchApi.semanticSearch(searchParams) as SearchResponse;
      
      setResults(response.results);
      setTotalResults(response.total_count);
      setPage(response.page);
      setExecutionTime(response.execution_time_ms);
      
    } catch (error) {
      console.error('搜索请求失败:', error);
      setResults([]);
      setTotalResults(0);
      setError('搜索请求失败，请稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (searchQuery: string) => {
    setQuery(searchQuery);
    setHasSearched(true);
    setPage(1); // 重置页码
    
    fetchSearchResults(searchQuery, 1);
  };

  // 处理分页
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    fetchSearchResults(query, newPage);
    
    // 滚动到页面顶部
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  };
  
  // 处理站点选择
  const handleSiteChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const siteId = event.target.value || null;
    setSelectedSiteId(siteId);
    
    // 如果已经搜索过，使用新选择的站点重新搜索
    if (hasSearched && query) {
      setPage(1);
      fetchSearchResults(query, 1);
    }
  };

  return (
    <div className="py-8">
      <div className="max-w-2xl mx-auto mb-8 text-center">
        <h1 className="text-3xl font-bold mb-4">SiteSearch</h1>
        <p className="text-muted-foreground mb-4">
          高性能网站搜索引擎，支持语义搜索和全文检索
        </p>
        
        {/* 站点选择 */}
        <div className="flex flex-col gap-4 mb-4">
          <div className="flex items-center justify-center">
            <span className="text-sm mr-2">选择站点:</span>
            <select
              value={selectedSiteId || ''}
              onChange={handleSiteChange}
              disabled={isLoadingSites}
              className="px-3 py-1 text-sm rounded-md bg-card border border-input focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">所有站点</option>
              {sites.map(site => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
            {isLoadingSites && <span className="ml-2 text-sm text-muted-foreground">加载中...</span>}
          </div>
        </div>
      </div>
      
      <SearchBar onSearch={handleSearch} />
      
      {/* 错误提示 */}
      {error && (
        <div className="w-full max-w-2xl mx-auto mt-4 p-3 bg-destructive/10 border border-destructive rounded-md text-center text-destructive">
          {error}
        </div>
      )}
      
      {hasSearched && (
        <>
          {/* 搜索统计信息 */}
          {(!isLoading && !error && results.length > 0) ? (
            <div className="w-full max-w-2xl mx-auto mt-4 mb-2">
              <p className="text-sm text-muted-foreground">
                找到 {totalResults} 条相关结果
                {executionTime !== null && ` (耗时 ${executionTime} 毫秒)`}
                {selectedSiteId && ' · 已筛选站点'}
              </p>
            </div>
          ): (
            <div className="w-full max-w-2xl mx-auto mt-4 mb-2 h-5">
            </div>
          )}
          
          <SearchResults 
            results={results} 
            isLoading={isLoading} 
            query={query} 
          />
          
          {/* 分页组件 */}
          {!isLoading && results.length > 0 && totalResults > pageSize && (
            <div className="w-full max-w-2xl mx-auto mt-8 flex justify-center">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1}
                  className="px-3 py-1 bg-card border border-border rounded-md disabled:opacity-50"
                >
                  上一页
                </button>
                <span className="text-sm">
                  第 {page} 页 / 共 {Math.ceil(totalResults / pageSize)} 页
                </span>
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= Math.ceil(totalResults / pageSize)}
                  className="px-3 py-1 bg-card border border-border rounded-md disabled:opacity-50"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
} 