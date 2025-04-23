import { useState, useEffect } from 'react';
import { Layout } from './components/layout/Layout';
import { SearchPage } from './pages/SearchPage';
import { SitesPage } from './pages/SitesPage';
import { MonitorPage } from './pages/MonitorPage';

type Route = '/' | '/sites' | '/monitor';

function App() {
  const [currentRoute, setCurrentRoute] = useState<Route>('/');

  // 简单的路由实现
  const renderPage = () => {
    switch (currentRoute) {
      case '/':
        return <SearchPage />;
      case '/sites':
        return <SitesPage />;
      case '/monitor':
        return <MonitorPage />;
      default:
        return <SearchPage />;
    }
  };

  // 监听Header中的导航点击
  const handleNavigation = (route: string) => {
    setCurrentRoute(route as Route);
  };

  // 挂载全局路由事件监听
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'BUTTON' && target.textContent) {
        if (target.textContent === '搜索') setCurrentRoute('/');
        if (target.textContent === '站点管理') setCurrentRoute('/sites');
        if (target.textContent === '爬取监控') setCurrentRoute('/monitor');
      }
    };

    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  return (
    <Layout>
      {renderPage()}
    </Layout>
  );
}

export default App
