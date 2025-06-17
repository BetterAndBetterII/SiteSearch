import { useState, useEffect } from 'react';
import { SearchBar } from '../components/search/SearchBar';
import { SearchResults } from '../components/search/SearchResults';
import { searchApi, siteApi } from '../api/index';
import { SearchResultItem, SearchResponse, SearchParams } from '../types/search';

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
  const [error, setError] = useState<string | null>(null);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null);
  const [isLoadingSites, setIsLoadingSites] = useState(false);
  
  // 新增高级搜索参数状态
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [searchParams, setSearchParams] = useState<SearchParams>({
    q: '',
    page: 1,
    page_size: 50,
    top_k: 20,
    similarity_cutoff: 0.6,
    rerank: true,
    rerank_top_k: 10
  });
  const [mimeTypeFilter, setMimeTypeFilter] = useState<string>('');

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
      // 更新查询和页码
      const updatedParams = {
        ...searchParams,
        q: searchQuery,
        page: currentPage,
      };
      
      // 如果选择了特定站点，添加站点ID参数
      if (selectedSiteId) {
        updatedParams.site_id = selectedSiteId;
      }
      
      // 如果选择了MIME类型筛选
      if (mimeTypeFilter) {
        updatedParams.mimetype = mimeTypeFilter;
      }
      
      // 调用语义搜索API
      const response = await searchApi.semanticSearch(updatedParams) as SearchResponse;
      
      setResults(response.results);
      setTotalResults(response.total_count);
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
    
    fetchSearchResults(searchQuery, 1);
  };
  
  // 处理站点选择
  const handleSiteChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const siteId = event.target.value || null;
    setSelectedSiteId(siteId);
  };
  
  // 处理MIME类型选择
  const handleMimeTypeChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setMimeTypeFilter(event.target.value);
  };
  
  // 处理高级参数变更
  const handleParamChange = (param: keyof SearchParams, value: any) => {
    setSearchParams(prev => ({
      ...prev,
      [param]: value
    }));
  };

  return (
    <div className="py-8">
      <div className="max-w-2xl mx-auto mb-8 text-center">
        <h1 className="text-3xl font-bold mb-4">SiteSearch</h1>
        <p className="text-muted-foreground mb-4">
          高性能网站搜索引擎，支持语义搜索和全文检索
        </p>
        
        {/* 基础筛选 */}
        <div className="flex flex-col gap-4 mb-4">
          <div className="flex items-center justify-center gap-4">
            <div className="flex items-center">
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
            
            <div className="flex items-center">
              <span className="text-sm mr-2">文件类型:</span>
              <select
                value={mimeTypeFilter}
                onChange={handleMimeTypeChange}
                className="px-3 py-1 text-sm rounded-md bg-card border border-input focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">全部类型</option>
                <option value="text/html">HTML</option>
                <option value="application/pdf">PDF</option>
                <option value="text/plain">文本</option>
                <option value="application/msword">Word</option>
                <option value="application/vnd.openxmlformats-officedocument.wordprocessingml.document">DOCX</option>
              </select>
            </div>
          </div>
          
          {/* 高级选项切换 */}
          <div className="flex justify-center">
            <button 
              onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
              className="text-sm text-primary hover:underline focus:outline-none"
            >
              {showAdvancedOptions ? '隐藏高级选项' : '显示高级选项'}
            </button>
          </div>
          
          {/* 高级搜索选项 */}
          {showAdvancedOptions && (
            <div className="border border-border rounded-md p-4 mt-2">
              <h3 className="text-sm font-medium mb-3">高级搜索选项</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Top-K 设置 */}
                <div className="flex flex-col">
                  <label className="text-sm mb-1">返回结果数量 (top_k)</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="1"
                      max="50"
                      value={searchParams.top_k || 20}
                      onChange={(e) => handleParamChange('top_k', parseInt(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-sm w-8 text-right">{searchParams.top_k || 20}</span>
                  </div>
                </div>
                
                {/* 相似度阈值 */}
                <div className="flex flex-col">
                  <label className="text-sm mb-1">相似度阈值 (similarity_cutoff)</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={searchParams.similarity_cutoff || 0.6}
                      onChange={(e) => handleParamChange('similarity_cutoff', parseFloat(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-sm w-12 text-right">{(searchParams.similarity_cutoff || 0.6).toFixed(2)}</span>
                  </div>
                </div>
                
                {/* 重排序选项 */}
                <div className="flex items-center">
                  <label className="text-sm mr-2">启用重排序:</label>
                  <input
                    type="checkbox"
                    checked={searchParams.rerank !== false}
                    onChange={(e) => handleParamChange('rerank', e.target.checked)}
                    className="h-4 w-4"
                  />
                </div>
                
                {/* 重排序 Top-K */}
                {searchParams.rerank !== false && (
                  <div className="flex flex-col">
                    <label className="text-sm mb-1">重排序数量 (rerank_top_k)</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="range"
                        min="5"
                        max="20"
                        value={searchParams.rerank_top_k || 10}
                        onChange={(e) => handleParamChange('rerank_top_k', parseInt(e.target.value))}
                        className="flex-1"
                      />
                      <span className="text-sm w-8 text-right">{searchParams.rerank_top_k || 10}</span>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="mt-3 flex flex-col gap-2">
                <div className="text-xs text-muted-foreground">
                  <p>提示: 调整这些参数可以影响搜索结果的质量和性能。更高的 top_k 值会返回更多结果但可能降低质量；更高的相似度阈值会提高结果精度但可能减少返回数量。</p>
                </div>
              </div>
            </div>
          )}
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
                {mimeTypeFilter && ' · 已筛选文件类型'}
                {searchParams.top_k !== 20 && ` · top_k=${searchParams.top_k}`}
                {searchParams.rerank && searchParams.rerank_top_k !== 10 && ` · rerank_top_k=${searchParams.rerank_top_k}`}
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
        </>
      )}
    </div>
  );
} 