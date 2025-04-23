import { useState } from 'react';
import { SearchBar } from '../components/search/SearchBar';
import { SearchResults } from '../components/search/SearchResults';

// 模拟数据
const mockResults = [
  {
    id: '1',
    title: 'SiteSearch - 高性能网站搜索引擎',
    url: 'https://example.com/sitesearch',
    snippet: 'SiteSearch是一个高性能的网站搜索引擎，支持全文检索和语义搜索。它能够爬取指定网站内容，清洗并索引数据，提供快速准确的搜索结果。',
    siteId: 'example',
    timestamp: '2025-04-23T12:00:00Z'
  },
  {
    id: '2',
    title: '如何使用SiteSearch进行站点配置',
    url: 'https://example.com/sitesearch/config',
    snippet: '本教程介绍如何配置SiteSearch来爬取您的网站。您可以设置起始URL、最大页面数、深度限制和URL过滤规则，以确保只爬取您需要的内容。',
    siteId: 'example',
    timestamp: '2025-04-22T15:30:00Z'
  },
  {
    id: '3',
    title: 'SiteSearch的爬虫与索引技术',
    url: 'https://example.com/sitesearch/technology',
    snippet: 'SiteSearch使用高性能爬虫框架Firecrawl和Httpx，结合Llama-index和Milvus向量库进行索引，提供准确的搜索结果和语义查询能力。',
    siteId: 'example',
    timestamp: '2025-04-21T09:15:00Z'
  }
];

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<typeof mockResults>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = (searchQuery: string) => {
    setQuery(searchQuery);
    setIsLoading(true);
    setHasSearched(true);
    
    // 模拟API请求延迟
    setTimeout(() => {
      setResults(mockResults.filter(item => 
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
        item.snippet.toLowerCase().includes(searchQuery.toLowerCase())
      ));
      setIsLoading(false);
    }, 800);
  };

  return (
    <div className="py-8">
      <div className="max-w-2xl mx-auto mb-8 text-center">
        <h1 className="text-3xl font-bold mb-4">SiteSearch</h1>
        <p className="text-muted-foreground mb-8">
          高性能网站搜索引擎，支持全文检索和语义搜索
        </p>
      </div>
      
      <SearchBar onSearch={handleSearch} />
      
      {hasSearched && (
        <SearchResults 
          results={results} 
          isLoading={isLoading} 
          query={query} 
        />
      )}
    </div>
  );
} 