import { useState } from 'react';
import { Button } from '../components/ui/button';

// 模拟数据
const mockSites = [
  {
    id: 'site1',
    name: '官方网站',
    baseUrl: 'https://example.com',
    description: '公司官方网站内容',
    urlPattern: 'https://(.*\\.example\\.com).*',
    maxUrls: 1000,
    maxDepth: 3,
    lastCrawled: '2025-04-22T10:30:00Z',
    pagesCrawled: 350,
    status: 'active'
  },
  {
    id: 'site2',
    name: '产品文档',
    baseUrl: 'https://docs.example.com',
    description: '产品使用文档',
    urlPattern: 'https://docs\\.example\\.com/.*',
    maxUrls: 500,
    maxDepth: 5,
    lastCrawled: '2025-04-20T15:45:00Z',
    pagesCrawled: 124,
    status: 'idle'
  }
];

type Site = typeof mockSites[0];

export function SitesPage() {
  const [sites, setSites] = useState<Site[]>(mockSites);
  const [showModal, setShowModal] = useState(false);
  
  const startCrawling = (siteId: string) => {
    console.log(`开始爬取站点: ${siteId}`);
    // 实际应用中这里会调用API启动爬虫
  };
  
  const stopCrawling = (siteId: string) => {
    console.log(`停止爬取站点: ${siteId}`);
    // 实际应用中这里会调用API停止爬虫
  };
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">站点管理</h1>
        <Button onClick={() => setShowModal(true)}>添加站点</Button>
      </div>
      
      <div className="grid gap-4">
        {sites.map((site) => (
          <div key={site.id} className="bg-card border border-border rounded-md p-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h3 className="text-lg font-medium">{site.name}</h3>
                <p className="text-sm text-muted-foreground">{site.baseUrl}</p>
              </div>
              <div className="flex space-x-2">
                {site.status === 'active' ? (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600"
                    onClick={() => stopCrawling(site.id)}
                  >
                    停止爬取
                  </Button>
                ) : (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => startCrawling(site.id)}
                  >
                    开始爬取
                  </Button>
                )}
                <Button variant="ghost" size="sm">设置</Button>
              </div>
            </div>
            
            <p className="text-sm mb-3">{site.description}</p>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">URL模式</p>
                <p className="font-mono text-xs bg-muted p-1 rounded mt-1 overflow-x-auto">
                  {site.urlPattern}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">爬取限制</p>
                <p>最大URL数: {site.maxUrls}, 最大深度: {site.maxDepth}</p>
              </div>
              <div>
                <p className="text-muted-foreground">上次爬取</p>
                <p>{new Date(site.lastCrawled).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-muted-foreground">爬取页面</p>
                <p>{site.pagesCrawled} 页</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
} 