/**
 * 单个工作进程的详细信息
 */
export interface WorkerDetail {
  pid: number;
  name: string;
  memory_rss_mb: number;
  cpu_percent: number;
  create_time: string;
}

/**
 * 队列的指标数据
 */
export interface QueueMetrics {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  avg_processing_time: number;
  last_activity: string | null;
}

/**
 * 组件（如cleaner, storage）的状态信息
 */
export interface ComponentStatus {
  type: string;
  active_processes: number;
  status: string;
  config: any; // 使用 any 因为配置结构多变
  queue_metrics: QueueMetrics;
  workers: WorkerDetail[];
  total_memory_rss_mb: number;
  total_cpu_percent: number;
}

/**
 * 爬取任务的状态信息
 */
export interface TaskStatus {
  task_id: string;
  start_url: string;
  site_id: string;
  max_urls: number;
  max_depth: number;
  regpattern: string;
  input_queue: string;
  crawler_workers: number;
  start_time: string;
  status: string;
  crawled_urls: number;
  crawler_config: any; // 使用 any 因为配置结构多变
  batch_size: number;
  sleep_time: number;
  queue_stats: QueueMetrics;
  active_processes: number;
  workers: WorkerDetail[];
  total_memory_rss_mb: number;
  total_cpu_percent: number;
  end_time?: string;
}

/**
 * 各组件工作进程的数量统计
 */
export interface WorkersCount {
  cleaner: number;
  storage: number;
  indexer: number;
  crawler: number;
  task_crawlers: Record<string, number>;
}

/**
 * 整体系统资源使用情况
 */
export interface SystemResources {
  cpu_percent: number;
  memory_percent: number;
  timestamp: string;
}

/**
 * 监控服务的状态
 */
export interface MonitoringStatus {
  is_active: boolean;
  interval: number;
}

/**
 * /api/status/ 接口返回的完整系统状态对象
 */
export interface RedisStats {
  redis_version: string;
  used_memory_human: string;
  used_memory_peak_human: string;
  total_system_memory_human: string;
  connected_clients: number;
  total_keys: number;
  uptime_in_days: number;
  error?: string;
}

export interface MainProcessResources {
  pid: number;
  name: string;
  memory_rss_mb: number;
  cpu_percent: number;
  error?: string;
}

export interface SystemStatus {
  components: Record<string, ComponentStatus>;
  queues: Record<string, QueueMetrics>;
  tasks: Record<string, TaskStatus>;
  workers_count: WorkersCount;
  system_resources: SystemResources;
  main_process_resources: MainProcessResources;
  redis_stats: RedisStats;
  monitoring: MonitoringStatus;
  timestamp: string;
} 