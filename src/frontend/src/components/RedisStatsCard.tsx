import { 
  Card, 
  CardContent,
  CardDescription, 
  CardHeader, 
  CardTitle 
} from './ui/card';
import { Badge } from './ui/badge';
import { Database, Server, MemoryStick, KeyRound, Users, Clock, AlertCircle } from 'lucide-react';
import { RedisStats } from '../api/types';

interface RedisStatsCardProps {
  stats: RedisStats;
}

export function RedisStatsCard({ stats }: RedisStatsCardProps) {
  if (stats.error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Database size={20} className="mr-2" />
            Redis 状态
          </CardTitle>
          <CardDescription>Redis 指标获取失败</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center text-red-500">
            <AlertCircle size={16} className="mr-2" />
            <p>{stats.error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-start">
            <div>
                <CardTitle className="flex items-center">
                    <Database size={20} className="mr-2" />
                    Redis 状态
                </CardTitle>
                <CardDescription>实时 Redis 数据库指标</CardDescription>
            </div>
            <Badge variant="success">运行中</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
          <div className="flex items-center">
            <Server size={16} className="mr-2 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">版本</p>
              <p className="font-semibold">{stats.redis_version}</p>
            </div>
          </div>
          <div className="flex items-center">
            <Clock size={16} className="mr-2 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">运行时长</p>
              <p className="font-semibold">{stats.uptime_in_days} 天</p>
            </div>
          </div>
          <div className="flex items-center">
            <MemoryStick size={16} className="mr-2 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">已用内存</p>
              <p className="font-semibold">{stats.used_memory_human}</p>
            </div>
          </div>
          <div className="flex items-center">
            <MemoryStick size={16} className="mr-2 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">峰值内存</p>
              <p className="font-semibold">{stats.used_memory_peak_human}</p>
            </div>
          </div>
           <div className="flex items-center">
            <KeyRound size={16} className="mr-2 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">总键数</p>
              <p className="font-semibold">{stats.total_keys}</p>
            </div>
          </div>
          <div className="flex items-center">
            <Users size={16} className="mr-2 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">连接数</p>
              <p className="font-semibold">{stats.connected_clients}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
} 