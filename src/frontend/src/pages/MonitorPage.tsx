import { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';

// 模拟数据
const mockQueueMetrics = {
  crawl: { pending: 125, processing: 8, completed: 1238, failed: 12 },
  clean: { pending: 23, processing: 2, completed: 1312, failed: 3 },
  storage: { pending: 5, processing: 1, completed: 1329, failed: 0 },
  index: { pending: 18, processing: 4, completed: 1210, failed: 7 }
};

const mockProcessStatus = [
  { id: 'crawler-1', type: 'crawler', status: 'running', uptime: '2h 15m', memory: '120MB', cpu: '0.8' },
  { id: 'crawler-2', type: 'crawler', status: 'running', uptime: '2h 15m', memory: '115MB', cpu: '0.7' },
  { id: 'cleaner-1', type: 'cleaner', status: 'running', uptime: '2h 15m', memory: '90MB', cpu: '0.5' },
  { id: 'storage-1', type: 'storage', status: 'running', uptime: '2h 15m', memory: '150MB', cpu: '0.4' },
  { id: 'indexer-1', type: 'indexer', status: 'running', uptime: '2h 15m', memory: '380MB', cpu: '1.2' },
  { id: 'indexer-2', type: 'indexer', status: 'running', uptime: '2h 15m', memory: '350MB', cpu: '1.0' }
];

type QueueMetric = {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
};

type QueueMetrics = {
  [key: string]: QueueMetric;
};

type ProcessStatus = {
  id: string;
  type: string;
  status: string;
  uptime: string;
  memory: string;
  cpu: string;
};

export function MonitorPage() {
  const [queueMetrics, setQueueMetrics] = useState<QueueMetrics>(mockQueueMetrics);
  const [processes, setProcesses] = useState<ProcessStatus[]>(mockProcessStatus);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  useEffect(() => {
    // 实际应用中，这里会设置定时刷新数据
    const interval = setInterval(() => {
      // 模拟数据变化
      setQueueMetrics(prev => ({
        ...prev,
        crawl: { 
          ...prev.crawl, 
          pending: Math.max(0, prev.crawl.pending - Math.floor(Math.random() * 3)),
          completed: prev.crawl.completed + Math.floor(Math.random() * 3)
        }
      }));
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);
  
  const refreshData = () => {
    setIsRefreshing(true);
    // 模拟API请求延迟
    setTimeout(() => {
      setIsRefreshing(false);
    }, 800);
  };
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">爬取监控</h1>
        <Button 
          variant="outline" 
          onClick={refreshData}
          disabled={isRefreshing}
        >
          {isRefreshing ? '刷新中...' : '刷新数据'}
        </Button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-card border border-border rounded-md p-4">
          <h2 className="text-lg font-medium mb-4">队列状态</h2>
          <div className="space-y-4">
            {Object.entries(queueMetrics).map(([queueName, metrics]) => (
              <div key={queueName} className="space-y-2">
                <div className="flex justify-between items-center">
                  <h3 className="font-medium capitalize">{queueName} 队列</h3>
                  <span className="text-xs px-2 py-1 bg-muted rounded-full">
                    {metrics.processing} 处理中
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-primary rounded-full"
                    style={{ width: `${Math.min(100, (metrics.completed / (metrics.completed + metrics.pending + metrics.processing + metrics.failed)) * 100)}%` }}
                  ></div>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>待处理: {metrics.pending}</span>
                  <span>已完成: {metrics.completed}</span>
                  <span>失败: {metrics.failed}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="bg-card border border-border rounded-md p-4">
          <h2 className="text-lg font-medium mb-4">进程状态</h2>
          <div className="space-y-3">
            {processes.map((process) => (
              <div key={process.id} className="flex items-center justify-between border-b border-border pb-2 last:border-0 last:pb-0">
                <div>
                  <div className="flex items-center">
                    <span className={`w-2 h-2 rounded-full mr-2 ${process.status === 'running' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                    <span className="font-medium capitalize">{process.type} {process.id.split('-')[1]}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">运行时间: {process.uptime}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm">内存: {process.memory}</p>
                  <p className="text-xs text-muted-foreground">CPU: {process.cpu}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="bg-card border border-border rounded-md p-4">
        <h2 className="text-lg font-medium mb-4">爬取日志</h2>
        <div className="bg-muted p-3 rounded-md font-mono text-xs h-60 overflow-y-auto">
          <p className="text-muted-foreground">[2025-04-23 12:30:45] INFO: 启动爬取进程 crawler-1</p>
          <p className="text-muted-foreground">[2025-04-23 12:30:45] INFO: 启动爬取进程 crawler-2</p>
          <p className="text-muted-foreground">[2025-04-23 12:30:46] INFO: 启动清洗进程 cleaner-1</p>
          <p className="text-muted-foreground">[2025-04-23 12:30:46] INFO: 启动存储进程 storage-1</p>
          <p className="text-muted-foreground">[2025-04-23 12:30:47] INFO: 启动索引进程 indexer-1</p>
          <p className="text-muted-foreground">[2025-04-23 12:30:47] INFO: 启动索引进程 indexer-2</p>
          <p className="text-green-500">[2025-04-23 12:31:02] INFO: 成功爬取页面 https://example.com/</p>
          <p className="text-green-500">[2025-04-23 12:31:05] INFO: 成功爬取页面 https://example.com/about</p>
          <p className="text-green-500">[2025-04-23 12:31:08] INFO: 成功爬取页面 https://example.com/products</p>
          <p className="text-yellow-500">[2025-04-23 12:31:10] WARNING: 页面加载超时 https://example.com/contact</p>
          <p className="text-red-500">[2025-04-23 12:31:15] ERROR: 无法访问页面 https://example.com/broken-link</p>
          <p className="text-green-500">[2025-04-23 12:31:25] INFO: 成功爬取页面 https://example.com/services</p>
        </div>
      </div>
    </div>
  );
} 