import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { SearchPage } from './pages/SearchPage';
import { SitesPage } from './pages/SitesPage';
import { MonitorPage } from './pages/MonitorPage';
import { CrawlPoliciesPage } from './pages/CrawlPoliciesPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { ToastProvider } from './components/ui/toast';

function App() {
  return (
    <Router>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </Router>
  );
}

function AppContent() {
  const location = useLocation();
  
  return (
    <Layout currentPath={location.pathname}>
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/sites" element={<SitesPage />} />
        <Route path="/sites/:siteId/policy" element={<CrawlPoliciesPage />} />
        <Route path="/sites/:siteId/documents" element={<DocumentsPage />} />
        <Route path="/monitor" element={<MonitorPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default App
